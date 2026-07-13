from fastapi.testclient import TestClient

from app.main import app
from app.models import FleetCaseRequest, Principal
from app.service import FleetFixService


def case_request(temperature: float = 109) -> FleetCaseRequest:
    return FleetCaseRequest(
        vehicle_id="TRK-4812",
        odometer_km=184200,
        dtc_codes=["P0217", "P0128"],
        engine_temperature_c=temperature,
        reported_symptom="Coolant warning and intermittent power reduction during loaded ascent.",
    )


def test_langgraph_workflow_coordinates_five_specialists() -> None:
    case = FleetFixService().open_case(case_request(), Principal(subject="tech-1", role="technician"))

    assert case.status.value == "requires_approval"
    assert [entry["agent"] for entry in case.trace] == [
        "telemetry_context", "diagnostic_specialist", "parts_specialist", "safety_specialist", "maintenance_planner"
    ]
    assert case.approval_required is True


def test_critical_safety_case_is_removed_from_service_but_still_requires_approval() -> None:
    case = FleetFixService().open_case(case_request(120), Principal(subject="tech-1", role="technician"))

    assert case.safety.remove_from_service is True
    assert case.safety.risk_level.value == "critical"
    assert case.status.value == "requires_approval"


def test_only_manager_can_approve_work_order() -> None:
    service = FleetFixService()
    case = service.open_case(case_request(), Principal(subject="tech-1", role="technician"))

    approved = service.approve(case.id, Principal(subject="manager-1", role="fleet_manager"))

    assert approved.status.value == "approved"
    assert approved.work_order_reference.startswith("WO-LOCAL-")


def test_case_api_exposes_approval_gated_workflow() -> None:
    client = TestClient(app)
    response = client.post("/api/cases", json=case_request().model_dump())

    assert response.status_code == 201
    assert response.json()["status"] == "requires_approval"
    assert response.headers["x-frame-options"] == "DENY"
