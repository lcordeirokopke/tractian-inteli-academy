

import operator
from typing import Annotated, Literal, Optional, TypedDict


class DecisionContext(TypedDict):
    analysis: Optional[dict]
    analyses: list[dict]
    data_quality: dict
    baseline: dict
    model: dict
    spectrum: Optional[dict]
    mode: str
    asset_id: str
    user_permissions: list[str]
    stop_policy_exhausted: bool


class DiagnosticOutput(TypedDict):
    analysis_summary: dict
    quality_flags: dict  # {"data_quality_ok": bool, "baseline_trustworthy": bool, "severity_critical": bool, ...}
    recommended_decision: Literal["orientar", "agir", "escalar"]
    decision_rationale: str
    supporting_evidence: list[dict]
    proposed_action: Optional[str]
    raw_context: DecisionContext  # contexto bruto embutido — o supervisor revalida a decisão sem
    # re-chamar MCP nem reconstruir campos a partir do resumo


class SupervisorState(TypedDict):
    case: dict
    user_context: dict
    diagnostic_result: Optional[DiagnosticOutput]
    decision: Optional[Literal["orientar", "agir", "escalar"]]
    action_result: Optional[dict]  # ActionResult da API {accepted, action_id, message} — quando a_permission_check
    # bloqueia preventivamente, produz um ActionResult sintético {accepted: False,
    # message: "..."} nesse mesmo campo; o supervisor sempre lê action_result.accepted
    # para rotear entre END e escalation_node na chamada pós-action_subgraph
    final_response: Optional[str]
    trace: Annotated[list[dict], operator.add]  # único campo com reducer


class DiagnosticState(TypedDict):
    case: dict
    user_context: dict
    plan: list[str]
    collected: dict[str, dict]  # tool_name -> envelope bruto {mode, notes, data} ou {"error": {...}}
    retry_count: dict[str, int]  # tool_name -> nº de retries já usados (máx 1, só partial/inconclusive)
    tool_call_count: int  # stop_policy (max_tool_calls=8)
    diagnostic_output: Optional[DiagnosticOutput]
    trace: Annotated[list[dict], operator.add]


class ActionState(TypedDict):
    case: dict
    user_context: dict
    diagnostic_result: DiagnosticOutput
    action_result: Optional[dict]  # ActionResult real da API OU sintético {accepted: False, message: ...}
    # produzido por a_permission_check quando bloqueia preventivamente
    trace: Annotated[list[dict], operator.add]
