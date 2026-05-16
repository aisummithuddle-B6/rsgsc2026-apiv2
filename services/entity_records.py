from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol


class EntityRecordRepositoryProtocol(Protocol):
    def list_top(
        self,
        collection_name: str,
        sort_field: str,
        sort_direction: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        ...


class EntityRecordRepository:
    def __init__(self, database) -> None:
        self.database = database

    def list_top(
        self,
        collection_name: str,
        sort_field: str,
        sort_direction: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        cursor = (
            self.database[collection_name]
            .find({})
            .sort(sort_field, sort_direction)
            .limit(limit)
        )
        return list(cursor)


@dataclass(frozen=True)
class EntityTopConfig:
    entity: str
    collection_name: str
    default_sort_field: str


def list_top_entity_records(
    repository: EntityRecordRepositoryProtocol,
    config: EntityTopConfig,
    count: int,
    sort_by: str | None,
    sort_order: str,
) -> dict[str, Any]:
    sort_field = sort_by or config.default_sort_field
    sort_direction = 1 if sort_order == "asc" else -1
    items = [
        _json_safe(document)
        for document in repository.list_top(
            collection_name=config.collection_name,
            sort_field=sort_field,
            sort_direction=sort_direction,
            limit=count,
        )
    ]

    return {
        "entity": config.entity,
        "count": count,
        "sortBy": sort_field,
        "sortOrder": sort_order,
        "items": items,
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        converted = {}
        for key, item in value.items():
            converted["id" if key == "_id" else key] = _json_safe(item)
        return converted

    if isinstance(value, list):
        return [_json_safe(item) for item in value]

    if isinstance(value, datetime | date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return float(value)

    if not isinstance(value, str | int | float | bool | type(None)):
        return str(value)

    return value
