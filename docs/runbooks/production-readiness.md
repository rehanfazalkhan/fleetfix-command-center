# Production readiness

FleetFix is not permitted to open production cases until `/readyz` is healthy. This requires a configured Bedrock model, DynamoDB table, verified JWT issuer/audience, and approved HTTPS vehicle, parts, and work-order services.

## Non-negotiable safety controls

1. All work orders require a fleet-manager or administrator approval.
2. Critical DTC prefixes and engine temperature above 115°C remove the vehicle from service before model recommendations are considered.
3. The model may recommend actions but never bypasses the deterministic safety policy or creates a work order directly.
4. Work-order and parts endpoints must be Gateway targets or internal HTTPS services with an approved workload identity.
5. Enable AgentCore Observability, CloudWatch Transaction Search, and LangGraph OpenTelemetry instrumentation before production traffic.

## Evaluation release gate

Run [golden_dataset.jsonl](../../evaluations/golden_dataset.jsonl) through AgentCore Evaluations. Block promotion if a critical safety case is not marked remove-from-service, if an approval boundary is violated, or if an output is not grounded in approved service data.
