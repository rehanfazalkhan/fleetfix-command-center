"""Explicit FleetFix configuration and production readiness controls."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    runtime_mode: str = "development"
    aws_region: str = "us-east-1"
    bedrock_model_id: str | None = None
    case_table: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None
    jwt_role_claim: str = "custom:role"
    vehicle_context_url: str | None = None
    parts_availability_url: str | None = None
    work_order_url: str | None = None

    @property
    def is_production(self) -> bool:
        return self.runtime_mode == "production"

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            runtime_mode=os.getenv("AGENTFORGE_RUNTIME_MODE", "development").lower(),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            bedrock_model_id=os.getenv("BEDROCK_MODEL_ID"),
            case_table=os.getenv("FLEETFIX_CASE_TABLE"),
            jwt_issuer=os.getenv("FLEETFIX_JWT_ISSUER"),
            jwt_audience=os.getenv("FLEETFIX_JWT_AUDIENCE"),
            jwt_role_claim=os.getenv("FLEETFIX_JWT_ROLE_CLAIM", "custom:role"),
            vehicle_context_url=os.getenv("FLEETFIX_VEHICLE_CONTEXT_URL"),
            parts_availability_url=os.getenv("FLEETFIX_PARTS_AVAILABILITY_URL"),
            work_order_url=os.getenv("FLEETFIX_WORK_ORDER_URL"),
        )

    def production_gaps(self) -> list[str]:
        if not self.is_production:
            return []
        values = {
            "BEDROCK_MODEL_ID": self.bedrock_model_id,
            "FLEETFIX_CASE_TABLE": self.case_table,
            "FLEETFIX_JWT_ISSUER": self.jwt_issuer,
            "FLEETFIX_JWT_AUDIENCE": self.jwt_audience,
            "FLEETFIX_VEHICLE_CONTEXT_URL": self.vehicle_context_url,
            "FLEETFIX_PARTS_AVAILABILITY_URL": self.parts_availability_url,
            "FLEETFIX_WORK_ORDER_URL": self.work_order_url,
        }
        return [key for key, value in values.items() if not value]

    def assert_production_ready(self) -> None:
        if self.runtime_mode not in {"development", "production"}:
            raise ConfigurationError("AGENTFORGE_RUNTIME_MODE must be development or production.")
        gaps = self.production_gaps()
        if gaps:
            raise ConfigurationError("Production configuration is incomplete: " + ", ".join(gaps))
