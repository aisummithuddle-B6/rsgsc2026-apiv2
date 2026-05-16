from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.insurance_poc_import import CLAIMS_COLLECTION
from app.services.entity_records import _json_safe


class FraudClaimRepositoryProtocol(Protocol):
    def get_claim(self, claim_id: str) -> dict[str, Any] | None:
        ...

    def list_related_claims(self, claim: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
        ...


class FraudClaimRepository:
    def __init__(self, database) -> None:
        self.database = database

    def get_claim(self, claim_id: str) -> dict[str, Any] | None:
        return self.database[CLAIMS_COLLECTION].find_one({"_id": claim_id})

    def list_related_claims(self, claim: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
        claim_id = claim.get("_id")
        related_filters = []
        for field in (
            "claimant.age",
            "claimant.gender",
            "claimant.ped_type",
            "policy.policy_zone",
            "hospitalization.diagnosis_category",
            "hospitalization.hospital_zone",
        ):
            value = get_nested_value(claim, field)
            if value is not None:
                related_filters.append({field: value})

        if not related_filters:
            return []

        cursor = (
            self.database[CLAIMS_COLLECTION]
            .find({"_id": {"$ne": claim_id}, "$or": related_filters})
            .limit(limit)
        )
        return list(cursor)


@dataclass(frozen=True)
class FraudRule:
    rule_id: str
    source: str
    score_impact: int
    reference_field_1: str
    reference_field_2: str
    comparison: str
    reason_builder: Callable[[dict[str, Any], list[dict[str, Any]]], str]
    evaluator: Callable[[dict[str, Any], list[dict[str, Any]]], bool]


class FraudRuleEngine:
    def __init__(self, rules: list[FraudRule] | None = None) -> None:
        self.rules = rules or DEFAULT_FRAUD_RULES

    def evaluate(
        self,
        claim: dict[str, Any],
        related_claims: list[dict[str, Any]],
    ) -> dict[str, Any]:
        reasons = []
        for rule in self.rules:
            if not rule.evaluator(claim, related_claims):
                continue

            reasons.append(
                {
                    "ruleId": rule.rule_id,
                    "source": rule.source,
                    "scoreImpact": rule.score_impact,
                    "reason": rule.reason_builder(claim, related_claims),
                    "referenceField1": rule.reference_field_1,
                    "referenceField2": rule.reference_field_2,
                    "comparison": rule.comparison,
                }
            )

        risk_score = min(sum(reason["scoreImpact"] for reason in reasons), 100)
        return {
            "riskScore": risk_score,
            "riskBand": _risk_band(risk_score),
            "evaluatedRuleCount": len(self.rules),
            "triggeredRuleCount": len(reasons),
            "reasons": reasons,
            "notEvaluated": NOT_EVALUATED_RULE_GROUPS,
        }


class FraudValidationAgent:
    def __init__(
        self,
        repository: FraudClaimRepositoryProtocol,
        rule_engine: FraudRuleEngine | None = None,
    ) -> None:
        self.repository = repository
        self.rule_engine = rule_engine or FraudRuleEngine()

    def validate_claim(self, claim_id: str) -> dict[str, Any] | None:
        claim = self.repository.get_claim(claim_id)
        if claim is None:
            return None

        related_claims = self.repository.list_related_claims(claim)
        result = self.rule_engine.evaluate(claim, related_claims)
        result["claimId"] = claim_id
        result["relatedRecordCount"] = len(related_claims)
        return _json_safe(result)


def get_nested_value(document: dict[str, Any], path: str, default: Any = None) -> Any:
    value: Any = document
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


def _is_truthy(document: dict[str, Any], path: str) -> bool:
    return bool(get_nested_value(document, path))


def _number(document: dict[str, Any], path: str) -> float:
    value = get_nested_value(document, path, 0)
    if value is None:
        return 0
    return float(value)


def _not_complete(value: Any) -> bool:
    return str(value or "").strip().lower() != "complete"


def _approved_low_settlement(claim: dict[str, Any]) -> bool:
    return (
        str(get_nested_value(claim, "settlement.claim_status", "")).lower() == "approved"
        and _number(claim, "financials.settlement_ratio_pct") < 30
    )


def _related_pattern_detected(
    claim: dict[str, Any],
    related_claims: list[dict[str, Any]],
) -> bool:
    if len(related_claims) < 3:
        return False

    diagnosis = get_nested_value(claim, "hospitalization.diagnosis_category")
    hospital_zone = get_nested_value(claim, "hospitalization.hospital_zone")
    matching = [
        related
        for related in related_claims
        if get_nested_value(related, "hospitalization.diagnosis_category") == diagnosis
        or get_nested_value(related, "hospitalization.hospital_zone") == hospital_zone
        or related.get("financials", {}).get("claim_amount_inr") is not None
    ]
    return len(matching) >= 3


def _risk_band(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    if score >= 20:
        return "Low"
    return "Minimal"


DEFAULT_FRAUD_RULES = [
    FraudRule(
        rule_id="health.high_claim_deviation",
        source="Health.csv",
        score_impact=18,
        reference_field_1="financials.standard_rate_deviation_pct",
        reference_field_2="financials.claim_amount_inr",
        comparison="> 100",
        evaluator=lambda claim, _: _number(claim, "financials.standard_rate_deviation_pct") > 100,
        reason_builder=lambda claim, _: (
            "Claim amount is "
            f"{_number(claim, 'financials.standard_rate_deviation_pct'):.2f}% "
            "above the standard rate."
        ),
    ),
    FraudRule(
        rule_id="health.high_coverage_ratio",
        source="Health.csv",
        score_impact=12,
        reference_field_1="financials.claim_coverage_ratio",
        reference_field_2="policy.sum_insured_inr",
        comparison="> 90",
        evaluator=lambda claim, _: _number(claim, "financials.claim_coverage_ratio") > 90,
        reason_builder=lambda claim, _: (
            "Claim coverage ratio is "
            f"{_number(claim, 'financials.claim_coverage_ratio'):.2f}%."
        ),
    ),
    FraudRule(
        rule_id="health.sum_insured_enhanced",
        source="Health.csv",
        score_impact=10,
        reference_field_1="policy.sum_insured_enhanced",
        reference_field_2="financials.claim_amount_inr",
        comparison="is true",
        evaluator=lambda claim, _: _is_truthy(claim, "policy.sum_insured_enhanced"),
        reason_builder=lambda *_: "Claim is from a policy with sum insured enhancement.",
    ),
    FraudRule(
        rule_id="health.zone_mismatch",
        source="Health.csv",
        score_impact=8,
        reference_field_1="financials.zone_mismatch",
        reference_field_2="policy.policy_zone",
        comparison="is true",
        evaluator=lambda claim, _: _is_truthy(claim, "financials.zone_mismatch"),
        reason_builder=lambda *_: "Claim has a policy/hospital zone mismatch.",
    ),
    FraudRule(
        rule_id="health.provider_blacklist",
        source="Health.csv",
        score_impact=20,
        reference_field_1="fraudRisk.provider_blacklist_flag",
        reference_field_2="hospitalization.hospital_accreditation",
        comparison="is true",
        evaluator=lambda claim, _: _is_truthy(claim, "fraudRisk.provider_blacklist_flag"),
        reason_builder=lambda *_: "Provider is marked as blacklisted.",
    ),
    FraudRule(
        rule_id="health.investigation_triggered",
        source="Health.csv",
        score_impact=8,
        reference_field_1="fraudRisk.investigation_triggered",
        reference_field_2="fraudRisk.investigation_outcome",
        comparison="is true",
        evaluator=lambda claim, _: _is_truthy(claim, "fraudRisk.investigation_triggered"),
        reason_builder=lambda *_: "Claim already triggered an investigation workflow.",
    ),
    FraudRule(
        rule_id="health.document_incomplete",
        source="Health.csv",
        score_impact=10,
        reference_field_1="documents.document_status",
        reference_field_2="documents.document_submission_mode",
        comparison="!= Complete",
        evaluator=lambda claim, _: _not_complete(get_nested_value(claim, "documents.document_status")),
        reason_builder=lambda *_: "Claim documents are not complete.",
    ),
    FraudRule(
        rule_id="health.late_claim_submission",
        source="Indicators-WC.csv",
        score_impact=8,
        reference_field_1="documents.claim_submission_timeline_days",
        reference_field_2="documents.document_status",
        comparison="> 30",
        evaluator=lambda claim, _: _number(claim, "documents.claim_submission_timeline_days") > 30,
        reason_builder=lambda claim, _: (
            "Claim was submitted "
            f"{_number(claim, 'documents.claim_submission_timeline_days'):.0f} days after the event."
        ),
    ),
    FraudRule(
        rule_id="health.repeated_claims",
        source="Health.csv",
        score_impact=10,
        reference_field_1="documents.previous_claims_count",
        reference_field_2="claimant.ped_type",
        comparison=">= 2",
        evaluator=lambda claim, _: _number(claim, "documents.previous_claims_count") >= 2,
        reason_builder=lambda claim, _: (
            "Claimant has "
            f"{_number(claim, 'documents.previous_claims_count'):.0f} previous claims."
        ),
    ),
    FraudRule(
        rule_id="health.sub_limit_exceeded",
        source="Health.csv",
        score_impact=10,
        reference_field_1="financials.disease_sub_limit_capped",
        reference_field_2="financials.sub_limit_excess_amount_inr",
        comparison="is true",
        evaluator=lambda claim, _: _is_truthy(claim, "financials.disease_sub_limit_capped"),
        reason_builder=lambda *_: "Claim exceeded a disease sub-limit.",
    ),
    FraudRule(
        rule_id="health.low_settlement_ratio_approved",
        source="Fraud_Scenarios.csv",
        score_impact=8,
        reference_field_1="financials.settlement_ratio_pct",
        reference_field_2="settlement.claim_status",
        comparison="< 30 AND Approved",
        evaluator=lambda claim, _: _approved_low_settlement(claim),
        reason_builder=lambda claim, _: (
            "Approved claim has low settlement ratio of "
            f"{_number(claim, 'financials.settlement_ratio_pct'):.2f}%."
        ),
    ),
    FraudRule(
        rule_id="health.high_hospital_risk",
        source="Health.csv",
        score_impact=8,
        reference_field_1="hospitalization.hospital_risk_score",
        reference_field_2="hospitalization.hospital_accreditation",
        comparison=">= 35",
        evaluator=lambda claim, _: _number(claim, "hospitalization.hospital_risk_score") >= 35,
        reason_builder=lambda claim, _: (
            "Hospital risk score is "
            f"{_number(claim, 'hospitalization.hospital_risk_score'):.1f}."
        ),
    ),
    FraudRule(
        rule_id="health.related_claim_pattern",
        source="Health.csv",
        score_impact=7,
        reference_field_1="relatedClaims",
        reference_field_2="hospitalization.diagnosis_category",
        comparison=">= 3 related records",
        evaluator=_related_pattern_detected,
        reason_builder=lambda _, related: (
            f"{len(related)} related claim records were found for comparable fields."
        ),
    ),
]

NOT_EVALUATED_RULE_GROUPS = [
    {
        "source": "Motor-Vehicle.csv",
        "reason": "Vehicle/VIN, title, lienholder, body shop, and police-report fields are not present in insurance_poc_claims.",
    },
    {
        "source": "Property.csv",
        "reason": "Property inventory, prior property loss, alarm, sale, and premises inspection fields are not present in insurance_poc_claims.",
    },
    {
        "source": "Fire.csv",
        "reason": "Fire scene, entry/exit, burn pattern, and missing-item fields are not present in insurance_poc_claims.",
    },
    {
        "source": "Theft.csv",
        "reason": "Theft-specific inventory, access, police, and ownership fields are not present in insurance_poc_claims.",
    },
    {
        "source": "Life_Insurance.csv",
        "reason": "Life insurance claimant, agent, doctor, diagnosis, and death/intimation fields are not present in insurance_poc_claims.",
    },
    {
        "source": "Indicators-WC.csv",
        "reason": "Employment change, witness, worksite, provider identity, and injury timing fields are only partially present.",
    },
]
