from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any


TENANT_ID = "sample.tenant.rmis"
ORGANIZATION_ID = "sample.organization.rmis"

CLAIMANTS = [
    ("Maya", "Reynolds", "Employee"),
    ("Ethan", "Brooks", "Third Party"),
    ("Sophia", "Carter", "Employee"),
    ("Noah", "Mitchell", "Contractor"),
    ("Olivia", "Bennett", "Visitor"),
]

CLAIM_TYPES = [
    "Workers Compensation",
    "General Liability",
    "Auto Liability",
    "Property",
    "Professional Liability",
]

STATUSES = ["Open", "In Review", "Closed", "Pending"]

CAUSES = [
    "Slip and fall",
    "Vehicle collision",
    "Equipment malfunction",
    "Water damage",
    "Customer injury",
    "Ergonomic strain",
    "Falling object",
    "Security incident",
    "Chemical exposure",
    "Weather event",
]


def build_sample_claimant_documents() -> list[dict[str, Any]]:
    created_at = datetime.now(UTC).isoformat()
    documents: list[dict[str, Any]] = []

    for claimant_index, (first_name, last_name, claimant_type) in enumerate(CLAIMANTS, start=1):
        claimant_id = f"sample.claimant.{claimant_index:03d}"
        full_name = f"{first_name} {last_name}"
        documents.append(
            {
                "_id": claimant_id,
                "documentType": "sample_claimant",
                "ClaimantId": claimant_id,
                "TenantId": TENANT_ID,
                "OrganizationId": ORGANIZATION_ID,
                "ClaimantType": claimant_type,
                "FirstName": first_name,
                "LastName": last_name,
                "FullName": full_name,
                "Email": f"{first_name.lower()}.{last_name.lower()}@example.com",
                "PhoneNumber": f"+1-555-010{claimant_index}",
                "EmployeeId": f"EMP-SAMPLE-{claimant_index:03d}",
                "CreatedAt": created_at,
                "claims": _build_claims_for_claimant(claimant_index, claimant_id, created_at),
            }
        )

    return documents


def _build_claims_for_claimant(
    claimant_index: int,
    claimant_id: str,
    created_at: str,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    base_loss_date = date(2026, 1, 3) + timedelta(days=(claimant_index - 1) * 7)

    for claim_index in range(1, 11):
        loss_date = base_loss_date + timedelta(days=claim_index * 3)
        reported_date = loss_date + timedelta(days=1)
        reserve_amount = Decimal("5000.00") + Decimal(claimant_index * 900 + claim_index * 275)
        paid_amount = reserve_amount * Decimal("0.35")

        claims.append(
            {
                "ClaimId": f"sample.claim.{claimant_index:03d}.{claim_index:03d}",
                "TenantId": TENANT_ID,
                "OrganizationId": ORGANIZATION_ID,
                "ClaimantId": claimant_id,
                "ClaimNumber": f"CLM-SAMPLE-{claimant_index:03d}-{claim_index:03d}",
                "ClaimType": CLAIM_TYPES[(claimant_index + claim_index - 2) % len(CLAIM_TYPES)],
                "Status": STATUSES[(claimant_index + claim_index - 2) % len(STATUSES)],
                "LossDate": loss_date.isoformat(),
                "ReportedDate": reported_date.isoformat(),
                "Description": (
                    f"Sample claim {claim_index} for claimant {claimant_index}."
                ),
                "CauseDescription": CAUSES[(claim_index - 1) % len(CAUSES)],
                "CurrentReserveAmount": float(reserve_amount),
                "TotalPaidAmount": float(paid_amount.quantize(Decimal("0.01"))),
                "CreatedAt": created_at,
                "UpdatedAt": created_at,
            }
        )

    return claims
