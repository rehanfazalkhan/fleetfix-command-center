"""FleetFix application service; a work order is impossible without an explicit human approval."""

from __future__ import annotations

from datetime import datetime, timezone

from .advisor import BedrockFleetAdvisor, DevelopmentFleetAdvisor, FleetAdvisor
from .clients import FleetServiceClients
from .config import Settings
from .models import CaseStatus, FleetCase, FleetCaseRequest, Principal
from .policy import PolicyViolation, authorize_approval, validate_case_input
from .repository import CaseRepository, build_repository
from .workflow import FleetFixWorkflow


class FleetFixService:
    def __init__(self, settings: Settings | None = None, repository: CaseRepository | None = None, advisor: FleetAdvisor | None = None) -> None:
        self.settings = settings or Settings.from_environment()
        self.repository = repository or build_repository(self.settings)
        self.clients = FleetServiceClients(self.settings)
        self.advisor = advisor or (BedrockFleetAdvisor(self.settings) if self.settings.is_production else DevelopmentFleetAdvisor())

    def open_case(self, request: FleetCaseRequest, principal: Principal) -> FleetCase:
        validate_case_input(request)
        if self.settings.is_production:
            self.settings.assert_production_ready()
        case = FleetFixWorkflow(self.clients, self.advisor).execute(request, principal)
        self.repository.save(case)
        return case

    def approve(self, case_id: str, principal: Principal) -> FleetCase:
        authorize_approval(principal.role)
        case = self.repository.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case.status != CaseStatus.REQUIRES_APPROVAL:
            raise PolicyViolation("Only a case awaiting approval can create a work order.")
        case.work_order_reference = self.clients.create_work_order(case.id, case.recommendation, principal)
        case.approved_by = principal.subject
        case.status = CaseStatus.APPROVED
        case.updated_at = datetime.now(timezone.utc)
        case.trace.append({"agent": "human_approval", "status": "approved", "approved_by": principal.subject})
        self.repository.save(case)
        return case

    def readiness(self) -> dict[str, object]:
        return {"ready": not self.settings.production_gaps(), "runtime_mode": self.settings.runtime_mode, "gaps": self.settings.production_gaps()}
