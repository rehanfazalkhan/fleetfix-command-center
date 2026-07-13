"""Bedrock-backed diagnostic and planning specialists with strict Pydantic output contracts."""

from __future__ import annotations

import json
from typing import Any, Protocol

from .config import Settings
from .models import DiagnosticAssessment, FleetCaseRequest, PartsAssessment, SafetyAssessment


class FleetAdvisor(Protocol):
    def diagnose(self, request: FleetCaseRequest, context: dict[str, Any]) -> tuple[DiagnosticAssessment, dict[str, int]]: ...
    def plan(self, diagnosis: DiagnosticAssessment, parts: PartsAssessment, safety: SafetyAssessment) -> tuple[str, dict[str, int]]: ...


class BedrockFleetAdvisor:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import boto3
            except ImportError as error:  # pragma: no cover
                raise RuntimeError("boto3 is required for Bedrock inference.") from error
            self._client = boto3.client("bedrock-runtime", region_name=self.settings.aws_region)
        return self._client

    def diagnose(self, request: FleetCaseRequest, context: dict[str, Any]) -> tuple[DiagnosticAssessment, dict[str, int]]:
        prompt = {"telemetry": request.model_dump(mode="json"), "vehicle_context": context, "output_schema": "probable_cause, confidence(0..1), recommended_actions[], required_parts[], rationale"}
        text, usage = self._converse("You are the FleetFix diagnostic specialist. Return only valid JSON. Never authorize a work order.", prompt)
        return DiagnosticAssessment.model_validate(self._json(text)), usage

    def plan(self, diagnosis: DiagnosticAssessment, parts: PartsAssessment, safety: SafetyAssessment) -> tuple[str, dict[str, int]]:
        prompt = {"diagnostic_assessment": diagnosis.model_dump(), "parts_assessment": parts.model_dump(), "safety_assessment": safety.model_dump(), "constraint": "Return a concise maintenance recommendation. State that manager approval is required before a work order is created."}
        return self._converse("You are the FleetFix maintenance planner. Use only the provided evidence. Never claim a work order was created.", prompt)

    def _converse(self, system: str, payload: dict[str, Any]) -> tuple[str, dict[str, int]]:
        response = self.client.converse(
            modelId=self.settings.bedrock_model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": json.dumps(payload)}]}],
            inferenceConfig={"maxTokens": 1000, "temperature": 0.1},
        )
        text = "".join(block.get("text", "") for block in response["output"]["message"].get("content", [])).strip()
        if not text:
            raise RuntimeError("Bedrock returned an empty specialist response.")
        usage = response.get("usage", {})
        return text, {"input_tokens": int(usage.get("inputTokens", 0)), "output_tokens": int(usage.get("outputTokens", 0)), "total_tokens": int(usage.get("totalTokens", 0))}

    @staticmethod
    def _json(text: str) -> dict[str, Any]:
        cleaned = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise RuntimeError("Diagnostic specialist did not return valid structured output.") from error
        if not isinstance(payload, dict):
            raise RuntimeError("Diagnostic specialist output must be a JSON object.")
        return payload


class DevelopmentFleetAdvisor:
    """Local contract implementation; production mode always uses BedrockFleetAdvisor."""

    def diagnose(self, request: FleetCaseRequest, context: dict[str, Any]) -> tuple[DiagnosticAssessment, dict[str, int]]:
        assessment = DiagnosticAssessment(probable_cause="Cooling-system performance degradation", confidence=0.82, recommended_actions=["Inspect coolant level and fan assembly", "Run pressure test before releasing vehicle"], required_parts=["COOLANT-HOSE-SET"], rationale="Telemetry and diagnostic codes indicate a cooling-path anomaly.")
        return assessment, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def plan(self, diagnosis: DiagnosticAssessment, parts: PartsAssessment, safety: SafetyAssessment) -> tuple[str, dict[str, int]]:
        return f"{diagnosis.recommended_actions[0]}. Parts availability is {parts.fulfilment_eta_hours} hours. {safety.rationale}. Fleet-manager approval is required before creating a work order.", {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
