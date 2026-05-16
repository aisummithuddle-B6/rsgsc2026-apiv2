from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Query

from app.core.config import get_settings
from app.core.documentdb import get_document_database
from app.services.entity_records import (
    EntityRecordRepository,
    EntityRecordRepositoryProtocol,
    EntityTopConfig,
    list_top_entity_records,
)


settings = get_settings()
app = FastAPI(title=settings.app_name)

INSURANCE_POC_CLAIMS = EntityTopConfig(
    entity="insurance_poc_claims",
    collection_name="insurance_poc_claims",
    default_sort_field="ingestedAt",
)
INSURANCE_POC_ENTITY_SCHEMAS = EntityTopConfig(
    entity="insurance_poc_entity_schemas",
    collection_name="insurance_poc_entity_schemas",
    default_sort_field="ingestedAt",
)
ENTITY_SCHEMAS = EntityTopConfig(
    entity="entity_schemas",
    collection_name="entity_schemas",
    default_sort_field="generatedAt",
)
SAMPLE_CLAIMANTS = EntityTopConfig(
    entity="sample_claimants",
    collection_name="sample_claimants",
    default_sort_field="CreatedAt",
)


def get_entity_record_repository() -> EntityRecordRepository:
    return EntityRecordRepository(get_document_database())


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/insurance-poc/claims/top", tags=["entities"])
def get_top_insurance_poc_claims(
    repository: Annotated[
        EntityRecordRepositoryProtocol,
        Depends(get_entity_record_repository),
    ],
    count: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> dict:
    return list_top_entity_records(
        repository=repository,
        config=INSURANCE_POC_CLAIMS,
        count=count,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@app.get("/insurance-poc/entity-schemas/top", tags=["entities"])
def get_top_insurance_poc_entity_schemas(
    repository: Annotated[
        EntityRecordRepositoryProtocol,
        Depends(get_entity_record_repository),
    ],
    count: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> dict:
    return list_top_entity_records(
        repository=repository,
        config=INSURANCE_POC_ENTITY_SCHEMAS,
        count=count,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@app.get("/entity-schemas/top", tags=["entities"])
def get_top_entity_schemas(
    repository: Annotated[
        EntityRecordRepositoryProtocol,
        Depends(get_entity_record_repository),
    ],
    count: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> dict:
    return list_top_entity_records(
        repository=repository,
        config=ENTITY_SCHEMAS,
        count=count,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@app.get("/sample-claimants/top", tags=["entities"])
def get_top_sample_claimants(
    repository: Annotated[
        EntityRecordRepositoryProtocol,
        Depends(get_entity_record_repository),
    ],
    count: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "desc",
) -> dict:
    return list_top_entity_records(
        repository=repository,
        config=SAMPLE_CLAIMANTS,
        count=count,
        sort_by=sort_by,
        sort_order=sort_order,
    )
