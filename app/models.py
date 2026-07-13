"""Typed contracts for fleet telemetry, AI assessments, and approval-controlled work orders."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CaseStatus(str, Enum):
    REQUIRES_APPROVAL = "requires_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    FAILED = "failed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FleetCaseRequest(BaseModel):
    vehicle_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,64}$")
    odometer_km: int = Field(ge=0, le=3_000_000)
    dtc_codes: list[str] = Field(min_length=1, max_length=20)
    engine_temperature_c: float = Field(ge=-40, le=250)
    reported_symptom: str = Field(min_length=3, max_length=1000)
    session_id: str | None = Field(default=None, max_length=128)


class Principal(BaseModel):
    subject: str
    role: str


class DiagnosticAssessment(BaseModel):
    probable_cause: str = Field(min_length=5, max_length=500)
    confidence: float = Field(ge=0, le=1)
    recommended_actions: list[str] = Field(min_length=1, max_length=5)
    required_parts: list[str] = Field(default_factory=list, max_length=10)
    rationale: str = Field(min_length=5, max_length=1000)


class PartsAssessment(BaseModel):
    available: bool
    fulfilment_eta_hours: int = Field(ge=0, le=720)
    sources: list[str] = Field(default_factory=list)


class SafetyAssessment(BaseModel):
    risk_level: RiskLevel
    remove_from_service: bool
    rationale: str


class FleetCase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    status: CaseStatus
    vehicle_id: str
    requested_by: str
    request: FleetCaseRequest
    vehicle_context: dict[str, Any] = Field(default_factory=dict)
    diagnostics: DiagnosticAssessment | None = None
    parts: PartsAssessment | None = None
    safety: SafetyAssessment | None = None
    recommendation: str = ""
    approval_required: bool = True
    approved_by: str | None = None
    work_order_reference: str | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
