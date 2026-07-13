"""LangGraph orchestration for fleet triage, diagnostics, parts, safety, and approval-ready planning."""

from __future__ import annotations

from typing import Any, TypedDict

from .advisor import FleetAdvisor
from .clients import FleetServiceClients
from .models import CaseStatus, FleetCase, FleetCaseRequest, Principal
from .policy import safety_assessment


class FleetState(TypedDict, total=False):
    request: FleetCaseRequest
    principal: Principal
    context: dict[str, Any]
    diagnostics: Any
    parts: Any
    safety: Any
    recommendation: str
    token_usage: dict[str, int]
    trace: list[dict[str, Any]]


class FleetFixWorkflow:
    def __init__(self, clients: FleetServiceClients, advisor: FleetAdvisor) -> None:
        self.clients = clients
        self.advisor = advisor

    def execute(self, request: FleetCaseRequest, principal: Principal) -> FleetCase:
        state = self._build_graph().invoke({"request": request, "principal": principal, "trace": [], "token_usage": {}})
        return FleetCase(
            status=CaseStatus.REQUIRES_APPROVAL,
            vehicle_id=request.vehicle_id,
            requested_by=principal.subject,
            request=request,
            vehicle_context=state["context"],
            diagnostics=state["diagnostics"],
            parts=state["parts"],
            safety=state["safety"],
            recommendation=state["recommendation"],
            trace=state["trace"],
            token_usage=state["token_usage"],
        )

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as error:  # pragma: no cover - installation dependency
            raise RuntimeError("langgraph is required to execute FleetFix workflows.") from error

        graph = StateGraph(FleetState)
        graph.add_node("telemetry_context", self._telemetry_context)
        graph.add_node("diagnostic_specialist", self._diagnostic_specialist)
        graph.add_node("parts_specialist", self._parts_specialist)
        graph.add_node("safety_specialist", self._safety_specialist)
        graph.add_node("maintenance_planner", self._maintenance_planner)
        graph.add_edge(START, "telemetry_context")
        graph.add_edge("telemetry_context", "diagnostic_specialist")
        graph.add_edge("diagnostic_specialist", "parts_specialist")
        graph.add_edge("parts_specialist", "safety_specialist")
        graph.add_edge("safety_specialist", "maintenance_planner")
        graph.add_edge("maintenance_planner", END)
        return graph.compile()

    def _telemetry_context(self, state: FleetState) -> dict[str, Any]:
        context = self.clients.vehicle_context(state["request"], state["principal"])
        return {"context": context, "trace": state["trace"] + [{"agent": "telemetry_context", "status": "completed"}]}

    def _diagnostic_specialist(self, state: FleetState) -> dict[str, Any]:
        diagnostics, usage = self.advisor.diagnose(state["request"], state["context"])
        return {"diagnostics": diagnostics, "token_usage": self._add_usage(state["token_usage"], usage), "trace": state["trace"] + [{"agent": "diagnostic_specialist", "status": "completed", "confidence": diagnostics.confidence}]}

    def _parts_specialist(self, state: FleetState) -> dict[str, Any]:
        parts = self.clients.parts(state["diagnostics"].required_parts, state["principal"])
        return {"parts": parts, "trace": state["trace"] + [{"agent": "parts_specialist", "status": "completed", "available": parts.available}]}

    def _safety_specialist(self, state: FleetState) -> dict[str, Any]:
        safety = safety_assessment(state["request"])
        return {"safety": safety, "trace": state["trace"] + [{"agent": "safety_specialist", "status": "completed", "risk": safety.risk_level.value}]}

    def _maintenance_planner(self, state: FleetState) -> dict[str, Any]:
        recommendation, usage = self.advisor.plan(state["diagnostics"], state["parts"], state["safety"])
        return {"recommendation": recommendation, "token_usage": self._add_usage(state["token_usage"], usage), "trace": state["trace"] + [{"agent": "maintenance_planner", "status": "completed", "approval_required": True}]}

    @staticmethod
    def _add_usage(current: dict[str, int], delta: dict[str, int]) -> dict[str, int]:
        return {key: current.get(key, 0) + delta.get(key, 0) for key in {"input_tokens", "output_tokens", "total_tokens"}}
