"""Case persistence with DynamoDB in production and an in-memory contract store locally."""

from __future__ import annotations

from typing import Protocol

from .config import Settings
from .models import FleetCase


class CaseRepository(Protocol):
    def save(self, case: FleetCase) -> None: ...
    def get(self, case_id: str) -> FleetCase | None: ...
    def list_recent(self) -> list[FleetCase]: ...


class InMemoryCaseRepository:
    def __init__(self) -> None:
        self.cases: dict[str, FleetCase] = {}

    def save(self, case: FleetCase) -> None:
        self.cases[case.id] = case

    def get(self, case_id: str) -> FleetCase | None:
        return self.cases.get(case_id)

    def list_recent(self) -> list[FleetCase]:
        return sorted(self.cases.values(), key=lambda item: item.created_at, reverse=True)[:100]


class DynamoCaseRepository:
    def __init__(self, settings: Settings) -> None:
        try:
            import boto3
        except ImportError as error:  # pragma: no cover
            raise RuntimeError("boto3 is required for FleetFix production persistence.") from error
        self.table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(settings.case_table)

    def save(self, case: FleetCase) -> None:
        self.table.put_item(Item={"case_id": case.id, "gsi_pk": "CASE", "gsi_sk": f"{case.created_at.isoformat()}#{case.id}", "payload": case.model_dump_json()})

    def get(self, case_id: str) -> FleetCase | None:
        item = self.table.get_item(Key={"case_id": case_id}).get("Item")
        return FleetCase.model_validate_json(item["payload"]) if item else None

    def list_recent(self) -> list[FleetCase]:
        response = self.table.query(IndexName="by_created", KeyConditionExpression="gsi_pk = :key", ExpressionAttributeValues={":key": "CASE"}, ScanIndexForward=False, Limit=100)
        return [FleetCase.model_validate_json(item["payload"]) for item in response.get("Items", [])]


def build_repository(settings: Settings) -> CaseRepository:
    if settings.is_production and not settings.production_gaps():
        return DynamoCaseRepository(settings)
    return InMemoryCaseRepository()
