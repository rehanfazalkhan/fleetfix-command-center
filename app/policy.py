"""Fleet safety and authority controls that model output cannot override."""

from __future__ import annotations

from .models import FleetCaseRequest, RiskLevel, SafetyAssessment


class PolicyViolation(ValueError):
    pass


CRITICAL_DTC_PREFIXES = ("P0", "C0", "B0")
VALID_ROLES = {"technician", "dispatcher", "fleet_manager", "admin"}


def validate_case_input(request: FleetCaseRequest) -> None:
    if any("ignore previous" in item.lower() for item in [request.reported_symptom, *request.dtc_codes]):
        raise PolicyViolation("The case was blocked by the input safety policy.")


def safety_assessment(request: FleetCaseRequest) -> SafetyAssessment:
    critical_code = any(code.upper().startswith(CRITICAL_DTC_PREFIXES) for code in request.dtc_codes)
    overheating = request.engine_temperature_c >= 115
    if critical_code or overheating:
        reason = "Critical diagnostic code" if critical_code else "Engine temperature exceeds operational threshold"
        return SafetyAssessment(risk_level=RiskLevel.CRITICAL, remove_from_service=True, rationale=reason)
    if request.engine_temperature_c >= 105:
        return SafetyAssessment(risk_level=RiskLevel.HIGH, remove_from_service=False, rationale="Elevated engine temperature requires same-day inspection")
    return SafetyAssessment(risk_level=RiskLevel.MEDIUM, remove_from_service=False, rationale="Maintenance decision requires a manager approval")


def authorize_approval(role: str) -> None:
    if role not in {"fleet_manager", "admin"}:
        raise PolicyViolation("Only a fleet manager or administrator may approve a work order.")
