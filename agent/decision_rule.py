"""Regra de decisão pura orientar/agir/escalar.

Este módulo não chama LLM, MCP nem
LangGraph — só recebe um `DecisionContext` já montado (por `d_evaluator`, Estágio 4, ou pelo
`supervisor`, Estágio 6) e devolve a decisão.

Thresholds abaixo são placeholders ilustrativos (ver regras-de-decisao.md, seção "Política de
parada") — não calibrados contra a distribuição real dos dados; permanecem como estão até uma
rodada de calibração deliberada (Fase 5), não são alterados como efeito colateral de nenhum outro
trabalho da Fase 2.
"""

from agent.state import DecisionContext

DATA_QUALITY_COMPLETENESS_MIN = 0.7
CONFIDENCE_ESCALATE_THRESHOLD = 0.5
MAX_TOOL_CALLS = 8
MAX_RETRIES_PER_TOOL = 1
SYSTEMATIC_ERROR_CONFIDENCE_MIN = 0.6
SYSTEMATIC_ERROR_MIN_SUSPECTS = 2
CONFLICT_CONFIDENCE_MARGIN = 0.15

action_permission_map = {
    "reprocess_analysis": "action_low",
    "request_specialist_analysis": "action_low",
    "update_asset_config": "action_high",
    "request_retraining": "action_high",
    "escalate_case": "escalate",
}

# Mapeamento tipo-de-falha -> palavras-chave observadas em `spectrum.peaks[].note` (glossário
# CONTEXTO_PROJETO.md §1.2). "imbalance"/"misalignment" ficam marcados como genéricos porque 1x/2x
# podem aparecer como subproduto de outras falhas (ex.: looseness também gera harmônicos) — ver
# SPECTRUM_GENERIC_TYPES abaixo e o desempate em `resolve_conflict`.
SPECTRUM_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "imbalance": ("1x",),
    "misalignment": ("2x",),
    "bearing_fault": ("bpfo", "bpfi", "bsf", "ftf"),
    "electrical_fault": ("linha", "line"),
    "looseness": ("subharm",),
    "lubrication": ("shock pulse", "atrito", "lubrific"),
}
SPECTRUM_GENERIC_TYPES = frozenset({"imbalance", "misalignment"})


def spectrum_confirms(analysis_type: str, peaks: list[dict]) -> bool:
    """Verifica se algum pico do espectro sustenta o tipo de falha candidato."""
    keywords = SPECTRUM_TYPE_KEYWORDS.get(analysis_type)
    if not keywords:
        return False
    for peak in peaks:
        note = (peak.get("note") or "").lower()
        if any(kw in note for kw in keywords):
            return True
    return False


def resolve_conflict(analyses: list[dict], spectrum: dict | None) -> dict | None:
    """Pesagem determinística entre fontes conflitantes: baseline > confiança > espectro
    (CONTEXTO_PROJETO.md §1.2, regra 7). Não reconsulta nenhuma tool — decide só sobre o que já foi
    coletado (ver camada-mcp-e-erros.md §2.1 sobre por que `conflict` não tem retry).

    Retorna a `Analysis` vencedora, ou `None` se a pesagem não resolveu (nesse caso o chamador deve
    escalar).
    """
    established = [a for a in analyses if a["baseline_state_at_detection"] == "established"]
    if len(established) == 1:
        return established[0]

    by_confidence = sorted(analyses, key=lambda a: a["confidence"], reverse=True)
    if len(by_confidence) >= 2:
        margin = by_confidence[0]["confidence"] - by_confidence[1]["confidence"]
        if margin >= CONFLICT_CONFIDENCE_MARGIN:
            return by_confidence[0]

    peaks = (spectrum or {}).get("peaks", [])
    matches = [a for a in analyses if spectrum_confirms(a["type"], peaks)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Desempate por especificidade: assinaturas específicas (BPFO/BPFI/BSF/FTF, subharmônico,
        # 2x-linha) pesam mais que harmônicos genéricos (1x/2x) quando ambos aparecem ao mesmo tempo
        # — ver caso real CEN-06 (M-205), onde um pico "2x" e um pico de subharmônico coexistem e a
        # resolução correta é looseness (subharmônico), não misalignment (2x).
        specific = [a for a in matches if a["type"] not in SPECTRUM_GENERIC_TYPES]
        if len(specific) == 1:
            return specific[0]
    return None


def systematic_error_evidence(asset_id: str, analyses: list[dict]) -> bool:
    """`analyses` já vem do que está em `DiagnosticState.collected["list_analyses"]` — a tool já
    terá sido chamada nos ramos onde essa função é usada, então nenhuma chamada MCP extra acontece
    aqui (`asset_id` mantido na assinatura só por clareza de leitura, não usado no corpo)."""
    suspects = [
        a
        for a in analyses
        if a["detection_mode"] == "baseline"
        and a["confidence"] >= SYSTEMATIC_ERROR_CONFIDENCE_MIN
        and a["baseline_state_at_detection"] in {"invalidated", "learning"}
    ]
    return len(suspects) >= SYSTEMATIC_ERROR_MIN_SUSPECTS


def _perm_ok(action: str | None, user_permissions: list[str]) -> bool:
    if action is None:
        return True
    required = action_permission_map.get(action)
    return required is not None and required in user_permissions


def _escalation_rationale(
    *,
    severity_critical: bool,
    mode: str | None,
    conflict_resolved: dict | None,
    candidate_action: str | None,
    user_permissions: list[str],
    stop_policy_exhausted: bool,
) -> str:
    if severity_critical:
        return "ESCALAR — severidade crítica."
    if mode == "unavailable":
        return "ESCALAR — dado indisponível (mode=unavailable), sem retry (camada-mcp-e-erros.md §2.1)."
    if mode == "conflict" and conflict_resolved is None:
        return "ESCALAR — conflito entre fontes não resolvido por pesagem de evidência (baseline/confiança/espectro)."
    if candidate_action is not None and not _perm_ok(candidate_action, user_permissions):
        return f"ESCALAR — ação necessária ({candidate_action}) requer permissão que o usuário não possui."
    if stop_policy_exhausted:
        return "ESCALAR — política de parada esgotada (max_tool_calls atingido sem dado suficiente)."
    return "ESCALAR — condição de escalonamento não classificada."


def apply_decision_rule(ctx: DecisionContext) -> dict:
    """Decide orientar/agir/escalar a partir de um `DecisionContext` já montado.

    Retorna um dict:
        {
            "recommended_decision": "orientar" | "agir" | "escalar",
            "candidate_action": str | None,
            "quality_flags": dict,       # {} na Passada 0 (nenhuma Analysis coletada)
            "decision_rationale": str,
        }
    """
    analysis = ctx.get("analysis")

    # Passada 0 — ticket de contextualização pura (CEN-11/13): nenhuma Analysis coletada, porque a
    # pergunta do cliente não depende de diagnóstico automático (regras-de-decisao.md §5.8).
    if analysis is None:
        return {
            "recommended_decision": "orientar",
            "candidate_action": None,
            "quality_flags": {},
            "decision_rationale": (
                "Ticket de contextualização pura — nenhuma Analysis coletada, decisão via Passada 0."
            ),
        }

    baseline = ctx.get("baseline") or {}
    data_quality = ctx.get("data_quality") or {}
    model = ctx.get("model") or {}
    analyses = ctx.get("analyses") or []
    spectrum = ctx.get("spectrum")
    mode = ctx.get("mode")
    user_permissions = ctx.get("user_permissions") or []
    stop_policy_exhausted = ctx.get("stop_policy_exhausted", False)
    detection_mode = analysis.get("detection_mode")

    # Passada 1 — candidate_action, SEM checar permissão ainda (só na Passada 2, ver §5.6).
    severity_critical = analysis.get("severity") == "critical"

    model_requirements = model.get("requirements") or {}
    data_quality_ok = (
        data_quality.get("completeness", 0) >= DATA_QUALITY_COMPLETENESS_MIN
        and data_quality.get("snr_db", 0) >= model_requirements.get("min_snr_db", 0)
        and not data_quality.get("staleness_flag", False)
    )

    baseline_trustworthy = detection_mode == "symptom" or (
        detection_mode == "baseline" and baseline.get("state") == "established"
    )

    conflict_resolved = resolve_conflict(analyses, spectrum) if mode == "conflict" else None

    coverage_entry = next(
        (c for c in model.get("coverage", []) if c.get("machine_type") == ctx.get("machine_type")),
        None,
    )
    can_learn_baseline = coverage_entry.get("can_learn_baseline") if coverage_entry else None

    systematic_error = systematic_error_evidence(ctx.get("asset_id", ""), analyses)

    candidate_action = None
    if analysis.get("status") == "stale" and baseline.get("state") == "invalidated":
        # CEN-07 — stale só é acionável junto com invalidated (CONTEXTO §1.2 regra 5; §5.2).
        candidate_action = "reprocess_analysis"
    elif analysis.get("status") == "pending" and model.get("processing_state") == "delayed":
        # CEN-02 — ausência de insight é atraso de processamento, não problema de dado (§5.4).
        candidate_action = "reprocess_analysis"
    elif mode == "conflict" and conflict_resolved is not None:
        # §5.5 — pesagem resolveu, mas ainda pede validação humana antes de ação corretiva maior.
        candidate_action = "request_specialist_analysis"
    elif detection_mode == "baseline" and can_learn_baseline is False and systematic_error:
        # CEN-09/16 — só dispara com padrão de erro sistemático, nunca insatisfação isolada (§5.4).
        candidate_action = "request_retraining"
    elif (
        analysis.get("confidence", 1.0) < CONFIDENCE_ESCALATE_THRESHOLD
        and analysis.get("severity") in {"medium", "high"}
        and analysis.get("status") == "current"
    ):
        # guarda "status == current" evita que CEN-05 (status=inconclusive) caia aqui (§5.7).
        candidate_action = "request_specialist_analysis"

    # Passada 2 — ESCALAR.
    escalate = (
        severity_critical
        or mode == "unavailable"
        or (mode == "conflict" and conflict_resolved is None)
        or (candidate_action is not None and not _perm_ok(candidate_action, user_permissions))
        or stop_policy_exhausted
    )

    quality_flags = {
        "severity_critical": severity_critical,
        "data_quality_ok": data_quality_ok,
        "baseline_trustworthy": baseline_trustworthy,
        "conflict_resolved": conflict_resolved is not None,
        "systematic_error_evidence": systematic_error,
    }

    # Passada 3 — AGIR se NOT ESCALAR e candidate_action calculado na Passada 1.
    if not escalate and candidate_action is not None:
        return {
            "recommended_decision": "agir",
            "candidate_action": candidate_action,
            "quality_flags": quality_flags,
            "decision_rationale": (
                f"AGIR via {candidate_action} — condições da Passada 1 satisfeitas, "
                "sem bloqueio de permissão/severidade/stop-policy na Passada 2."
            ),
        }

    if escalate:
        return {
            "recommended_decision": "escalar",
            "candidate_action": candidate_action,
            "quality_flags": quality_flags,
            "decision_rationale": _escalation_rationale(
                severity_critical=severity_critical,
                mode=mode,
                conflict_resolved=conflict_resolved,
                candidate_action=candidate_action,
                user_permissions=user_permissions,
                stop_policy_exhausted=stop_policy_exhausted,
            ),
        }

    # ORIENTAR — else incondicional (§5.7), não um OU de sub-casos.
    return {
        "recommended_decision": "orientar",
        "candidate_action": None,
        "quality_flags": quality_flags,
        "decision_rationale": "ORIENTAR via else — nenhuma condição de ESCALAR nem candidate_action aplicável.",
    }
