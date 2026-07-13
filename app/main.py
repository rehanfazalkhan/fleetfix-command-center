"""FleetFix API and AgentCore Runtime HTTP adapter."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthenticationError, authenticate
from .models import FleetCase, FleetCaseRequest
from .policy import PolicyViolation
from .service import FleetFixService

BASE_DIR = Path(__file__).resolve().parent.parent
service = FleetFixService()
app = FastAPI(title="FleetFix Command Center", version="1.0.0", description="LangGraph fleet diagnostics with Bedrock, safety controls, and approval-gated work orders.")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "public, max-age=300"
    return response


def principal(development_role: str, authorization: str | None):
    try:
        return authenticate(authorization, service.settings, development_role)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health() -> dict[str, object]:
    return {"service": "fleetfix-command-center", **service.readiness()}


@app.get("/readyz")
def readyz(response: Response) -> dict[str, object]:
    readiness = service.readiness()
    if not readiness["ready"]:
        response.status_code = 503
    return readiness


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "Healthy"}


@app.get("/api/cases", response_model=list[FleetCase])
def cases() -> list[FleetCase]:
    return service.repository.list_recent()


@app.post("/api/cases", response_model=FleetCase, status_code=201)
def open_case(request: FleetCaseRequest, authorization: str | None = Header(default=None), actor_role: str = Header(default="technician", alias="X-FleetFix-Development-Role")) -> FleetCase:
    try:
        return service.open_case(request, principal(actor_role, authorization))
    except PolicyViolation as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/cases/{case_id}/approve", response_model=FleetCase)
def approve_case(case_id: str, authorization: str | None = Header(default=None), actor_role: str = Header(default="fleet_manager", alias="X-FleetFix-Development-Role")) -> FleetCase:
    request = FleetCaseRequest(vehicle_id="approval-context", odometer_km=0, dtc_codes=["P1000"], engine_temperature_c=0, reported_symptom="approval")
    try:
        return service.approve(case_id, principal(actor_role, authorization))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Case not found") from error
    except PolicyViolation as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/invocations", response_model=FleetCase)
def agentcore_invocation(payload: dict, authorization: str | None = Header(default=None)) -> FleetCase:
    try:
        request = FleetCaseRequest.model_validate(payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Fleet telemetry payload is invalid.") from error
    return open_case(request, authorization, "technician")
