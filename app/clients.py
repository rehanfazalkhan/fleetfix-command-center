"""Production HTTPS integrations; local fixtures exist strictly for contract development."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings
from .models import FleetCaseRequest, PartsAssessment, Principal


class FleetServiceClients:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def vehicle_context(self, request: FleetCaseRequest, principal: Principal) -> dict[str, Any]:
        if not self.settings.is_production:
            return {"vehicle_id": request.vehicle_id, "model": "Class 8 tractor", "open_campaigns": [], "last_service_km": max(0, request.odometer_km - 12_400), "telemetry_window_minutes": 30}
        return self._post(self.settings.vehicle_context_url, {"vehicle_id": request.vehicle_id, "odometer_km": request.odometer_km}, principal)

    def parts(self, required_parts: list[str], principal: Principal) -> PartsAssessment:
        if not self.settings.is_production:
            return PartsAssessment(available=True, fulfilment_eta_hours=4, sources=["regional-distribution-center"])
        payload = self._post(self.settings.parts_availability_url, {"part_numbers": required_parts}, principal)
        return PartsAssessment.model_validate(payload)

    def create_work_order(self, case_id: str, recommendation: str, principal: Principal) -> str:
        if not self.settings.is_production:
            return f"WO-LOCAL-{case_id[:8].upper()}"
        payload = self._post(self.settings.work_order_url, {"case_id": case_id, "recommendation": recommendation}, principal)
        reference = payload.get("work_order_reference")
        if not reference:
            raise RuntimeError("Work-order service did not return a reference.")
        return str(reference)

    def _post(self, endpoint: str | None, payload: dict[str, Any], principal: Principal) -> dict[str, Any]:
        if not endpoint or not endpoint.startswith("https://"):
            raise RuntimeError("FleetFix production integrations require approved HTTPS endpoints.")
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "X-FleetFix-Subject": principal.subject, "X-FleetFix-Role": principal.role},
        )
        try:
            with urlopen(request, timeout=8) as response:  # nosec B310 - HTTPS is required above
                data = json.loads(response.read().decode("utf-8"))
                if not isinstance(data, dict):
                    raise RuntimeError("Fleet service returned a malformed response.")
                return data
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError("Approved fleet service is unavailable; no work order was created.") from error
