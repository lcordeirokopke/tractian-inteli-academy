"""Testes unitários de `apply_decision_rule` — Estágio 2 do plano de execução Fase 2.

Cobre no mínimo CEN-03, CEN-05, CEN-06, CEN-07, CEN-08, CEN-09, CEN-11/13, CEN-16
(`eval/test-scenarios.md`, usado só para montar fixtures — nunca `eval/expected-paths.json`).

Onde possível os fixtures reproduzem payloads reais obtidos ao vivo da API local (`seed=complete`)
em 2026-08-31/09-01; onde os dados reais não bastam para exercitar um ramo específico da regra
(CEN-16), o fixture é sintético — anotado no teste correspondente. Ver `case/plano-feito.md`
(Estágio 2) para as limitações de calibração encontradas nesse processo.

Testa só a função pura — sem LLM, MCP ou LangGraph.
"""

from agent.decision_rule import (
    apply_decision_rule,
    resolve_conflict,
    spectrum_confirms,
    systematic_error_evidence,
)


def _ctx(**overrides):
    base = {
        "analysis": None,
        "analyses": [],
        "data_quality": {},
        "baseline": {},
        "model": {},
        "spectrum": None,
        "mode": "complete",
        "asset_id": "asset_test",
        "machine_type": "motor_induction",
        "user_permissions": [],
        "stop_policy_exhausted": False,
    }
    base.update(overrides)
    return base


# -- CEN-11/13 — contextualização pura (Passada 0) --------------------------------------------


def test_cen_11_13_contextualizacao_pura_orienta_via_passada_0():
    ctx = _ctx(analysis=None)
    result = apply_decision_rule(ctx)
    assert result["recommended_decision"] == "orientar"
    assert result["candidate_action"] is None
    assert result["quality_flags"] == {}


# -- CEN-03 — S-420, falso positivo por baseline invalidated + conflito com looseness ----------


def test_cen_03_conflito_resolvido_mas_sem_permissao_escala():
    # dados reais: GET /assets/asset_S420/analyses?seed=complete
    analyses = [
        {
            "id": "an_9903",
            "type": "imbalance",
            "detection_mode": "baseline",
            "severity": "medium",
            "confidence": 0.81,
            "baseline_state_at_detection": "invalidated",
            "status": "current",
        },
        {
            "id": "an_9904",
            "type": "looseness",
            "detection_mode": "baseline",
            "severity": "low",
            "confidence": 0.66,
            "baseline_state_at_detection": "established",
            "status": "current",
        },
    ]
    ctx = _ctx(
        analysis=analyses[0],
        analyses=analyses,
        baseline={"state": "invalidated"},
        mode="conflict",
        machine_type="spindle",
        user_permissions=["read"],  # usr_bruno (Operador de Usinagem) — só read
    )
    result = apply_decision_rule(ctx)
    # resolve_conflict resolve por baseline (único established = looseness) antes de chegar no
    # espectro — conflict_resolved=True, mas falta action_low para request_specialist_analysis.
    assert result["quality_flags"]["conflict_resolved"] is True
    assert result["quality_flags"]["baseline_trustworthy"] is False
    assert result["candidate_action"] == "request_specialist_analysis"
    assert result["recommended_decision"] == "escalar"


# -- CEN-05 — M-605, inferência incerta (analysis.status=inconclusive) -------------------------


def test_cen_05_analise_inconclusiva_orienta():
    # dados reais: GET /analyses/an_9910?seed=complete (electrical_fault, banda 2x-linha ausente)
    analysis = {
        "id": "an_9910",
        "type": "electrical_fault",
        "detection_mode": "baseline",
        "severity": "low",
        "confidence": 0.41,
        "baseline_state_at_detection": "established",
        "status": "inconclusive",
    }
    ctx = _ctx(
        analysis=analysis,
        analyses=[analysis],
        baseline={"state": "established"},
        mode="complete",
        machine_type="motor_induction",
        user_permissions=["read"],
    )
    result = apply_decision_rule(ctx)
    # guarda "status == current" barra o ramo request_specialist_analysis (§5.7) — sem ela,
    # confidence=0.41 < 0.5 e severity fora de {medium, high} já bastariam para não bater de qualquer
    # forma, mas o ponto central do teste é a guarda de status.
    assert result["candidate_action"] is None
    assert result["recommended_decision"] == "orientar"


# -- CEN-06 — M-205, conflito misalignment vs. looseness, subharmônicos sustentam looseness ----


def test_cen_06_espectro_desempata_por_especificidade_looseness_vence_2x_generico():
    # dados reais: GET /assets/asset_M205/analyses e /spectrum?seed=complete — ambas analyses têm
    # baseline_state_at_detection=established (tier 1 não desempata) e confiança quase empatada
    # (0.69 vs 0.71, diff 0.02 < 0.15 — tier 2 não desempata); espectro tem pico "2x" (misalignment)
    # E pico de subharmônico (looseness) ao mesmo tempo — tier 3 precisa do desempate por
    # especificidade (Divergência 4 do Estágio 2, resolvida com o usuário).
    analyses = [
        {
            "id": "an_9907",
            "type": "misalignment",
            "detection_mode": "baseline",
            "severity": "medium",
            "confidence": 0.69,
            "baseline_state_at_detection": "established",
            "status": "current",
        },
        {
            "id": "an_9908",
            "type": "looseness",
            "detection_mode": "baseline",
            "severity": "medium",
            "confidence": 0.71,
            "baseline_state_at_detection": "established",
            "status": "current",
        },
    ]
    spectrum = {
        "peaks": [
            {"freq_hz": 4.0, "amplitude_mm_s": 1.3, "note": "2x"},
            {"freq_hz": 2.0, "amplitude_mm_s": 0.9, "note": "0.5x/subharmônico (looseness)"},
        ]
    }
    resolved = resolve_conflict(analyses, spectrum)
    assert resolved is not None
    assert resolved["type"] == "looseness"

    ctx = _ctx(
        analysis=analyses[0],
        analyses=analyses,
        baseline={"state": "established"},
        spectrum=spectrum,
        mode="conflict",
        machine_type="mill",
        user_permissions=["read", "action_high"],  # usr_carla — sem action_low
    )
    result = apply_decision_rule(ctx)
    assert result["quality_flags"]["conflict_resolved"] is True
    assert result["candidate_action"] == "request_specialist_analysis"
    # sem action_low, mesmo com o conflito resolvido, escala (Passada 2 — permissão)
    assert result["recommended_decision"] == "escalar"


# -- CEN-07 — B-204, stale + baseline invalidated -> reprocessar ------------------------------


def test_cen_07_stale_e_invalidated_juntos_agir_reprocess():
    # dados reais: GET /analyses/an_9906 e /baseline?seed=complete
    analysis = {
        "id": "an_9906",
        "type": "bearing_fault",
        "detection_mode": "baseline",
        "severity": "high",
        "confidence": 0.75,
        "baseline_state_at_detection": "invalidated",
        "status": "stale",
    }
    ctx = _ctx(
        analysis=analysis,
        analyses=[analysis],
        baseline={"state": "invalidated"},
        model={"processing_state": "idle"},
        mode="complete",
        machine_type="pump",
        user_permissions=["read", "action_low"],  # Mecânico
    )
    result = apply_decision_rule(ctx)
    assert result["candidate_action"] == "reprocess_analysis"
    assert result["recommended_decision"] == "agir"


def test_stale_sozinho_sem_invalidated_nao_aciona_reprocess():
    # §5.2 — stale sem invalidated não é acionável (contraste com o teste acima).
    analysis = {
        "id": "an_x",
        "type": "bearing_fault",
        "detection_mode": "baseline",
        "severity": "high",
        "confidence": 0.75,
        "baseline_state_at_detection": "established",
        "status": "stale",
    }
    ctx = _ctx(
        analysis=analysis,
        analyses=[analysis],
        baseline={"state": "established"},
        user_permissions=["read", "action_low"],
    )
    result = apply_decision_rule(ctx)
    assert result["candidate_action"] is None


# -- CEN-08 — V-301, confiança alta + qualidade de dado baixa (tensão) -------------------------


def test_cen_08_confianca_alta_qualidade_baixa_orienta_sem_agir():
    # dados reais: GET /analyses/an_9909, /data-quality, /models/mdl_vib_v3?seed=complete
    analysis = {
        "id": "an_9909",
        "type": "imbalance",
        "detection_mode": "baseline",
        "severity": "medium",
        "confidence": 0.83,
        "baseline_state_at_detection": "established",
        "status": "current",
    }
    ctx = _ctx(
        analysis=analysis,
        analyses=[analysis],
        baseline={"state": "established"},
        data_quality={"completeness": 0.62, "snr_db": 8.4, "staleness_flag": True},
        model={
            "requirements": {"min_completeness": 0.8, "min_snr_db": 12.0},
            "coverage": [{"machine_type": "fan", "supported": True, "can_learn_baseline": True}],
            "processing_state": "delayed",
        },
        machine_type="fan",
        mode="complete",
        user_permissions=["read", "action_low"],
    )
    result = apply_decision_rule(ctx)
    assert result["quality_flags"]["data_quality_ok"] is False
    assert result["quality_flags"]["baseline_trustworthy"] is True
    # tensão documentada em quality_flags, mas nenhuma condição de ESCALAR/AGIR dispara (§5.7)
    assert result["candidate_action"] is None
    assert result["recommended_decision"] == "orientar"


# -- CEN-09 — M-102, motor DC, cobertura sem aprendizado de baseline ---------------------------


def test_cen_09_sem_analises_reais_orienta_via_passada_0():
    # dados reais: GET /assets/asset_M102/analyses?seed=complete devolve lista vazia — o motor DC
    # nunca teve uma Analysis baseline-mode gerada (consistente com can_learn_baseline=false: o
    # modelo nunca produziu detecção por desvio pra esse ativo). analysis=None -> Passada 0.
    ctx = _ctx(analysis=None, analyses=[], machine_type="motor_dc")
    result = apply_decision_rule(ctx)
    assert result["recommended_decision"] == "orientar"


def test_cen_09_variante_cobertura_sem_erro_sistematico_orienta_via_else():
    # variante sintética (§5.4 "ressalva de calibração"): se existisse uma Analysis baseline-mode
    # para o motor DC mas sem 2 suspeitos de erro sistemático, o ramo request_retraining não dispara
    # e o caso cai no else (não na Passada 0) — exercitando o outro caminho de código pro mesmo
    # desfecho documentado (orientar).
    analysis = {
        "id": "an_hyp",
        "type": "none",
        "detection_mode": "baseline",
        "severity": "none",
        "confidence": 0.5,
        "baseline_state_at_detection": "learning",
        "status": "current",
    }
    ctx = _ctx(
        analysis=analysis,
        analyses=[analysis],
        baseline={"state": "learning"},
        model={
            "coverage": [{"machine_type": "motor_dc", "supported": True, "can_learn_baseline": False}],
            "processing_state": "idle",
        },
        machine_type="motor_dc",
        user_permissions=["read", "action_high"],
    )
    result = apply_decision_rule(ctx)
    assert result["candidate_action"] is None
    assert result["recommended_decision"] == "orientar"


# -- CEN-16 — S-420, retreinamento por erro sistemático (fixture sintético) --------------------


def test_cen_16_erro_sistematico_com_lacuna_de_cobertura_aciona_retraining():
    # Divergência 5 do Estágio 2: com os dados reais de asset_S420 (spindle, can_learn_baseline=True
    # e só 1 análise "suspeita"), o único ramo documentado de request_retraining NUNCA dispara —
    # ele exige can_learn_baseline==False (história do CEN-09), enquanto o CEN-16 real é sobre erro
    # sistemático num tipo de máquina que o modelo cobre. Decisão registrada com o usuário: manter a
    # regra exatamente como documentada e testar aqui com um fixture sintético que efetivamente
    # satisfaz as 3 condições do ramo, para validar que o código faz o que a regra diz — não que
    # reproduz literalmente os dados seedados do S-420 (ver plano-feito.md, Estágio 2).
    analyses = [
        {
            "id": "an_x1",
            "type": "imbalance",
            "detection_mode": "baseline",
            "severity": "medium",
            "confidence": 0.81,
            "baseline_state_at_detection": "invalidated",
            "status": "current",
        },
        {
            "id": "an_x2",
            "type": "imbalance",
            "detection_mode": "baseline",
            "severity": "medium",
            "confidence": 0.7,
            "baseline_state_at_detection": "learning",
            "status": "current",
        },
    ]
    ctx = _ctx(
        analysis=analyses[0],
        analyses=analyses,
        baseline={"state": "invalidated"},
        model={
            "coverage": [{"machine_type": "spindle", "supported": True, "can_learn_baseline": False}],
            "processing_state": "idle",
        },
        machine_type="spindle",
        mode="complete",
        user_permissions=["read", "action_high"],  # Engenheiro de Manutenção
    )
    result = apply_decision_rule(ctx)
    assert result["quality_flags"]["systematic_error_evidence"] is True
    assert result["candidate_action"] == "request_retraining"
    assert result["recommended_decision"] == "agir"


# -- Estrutural: Passada 2 (severidade crítica, unavailable, stop-policy) ----------------------


def test_severidade_critica_escala_mesmo_sem_candidate_action():
    analysis = {
        "id": "an_c",
        "type": "bearing_fault",
        "detection_mode": "baseline",
        "severity": "critical",
        "confidence": 0.9,
        "baseline_state_at_detection": "established",
        "status": "current",
    }
    ctx = _ctx(analysis=analysis, analyses=[analysis], baseline={"state": "established"})
    result = apply_decision_rule(ctx)
    assert result["recommended_decision"] == "escalar"


def test_mode_unavailable_escala_imediatamente_sem_retry():
    analysis = {
        "id": "an_u",
        "type": "none",
        "detection_mode": "baseline",
        "severity": "none",
        "confidence": 0.5,
        "baseline_state_at_detection": "established",
        "status": "current",
    }
    ctx = _ctx(analysis=analysis, analyses=[analysis], baseline={"state": "established"}, mode="unavailable")
    result = apply_decision_rule(ctx)
    assert result["recommended_decision"] == "escalar"


def test_stop_policy_exhausted_forca_escalar():
    analysis = {
        "id": "an_s",
        "type": "none",
        "detection_mode": "baseline",
        "severity": "none",
        "confidence": 0.5,
        "baseline_state_at_detection": "established",
        "status": "current",
    }
    ctx = _ctx(
        analysis=analysis,
        analyses=[analysis],
        baseline={"state": "established"},
        stop_policy_exhausted=True,
    )
    result = apply_decision_rule(ctx)
    assert result["recommended_decision"] == "escalar"


# -- Helpers isolados -----------------------------------------------------------------------


def test_systematic_error_evidence_exige_ao_menos_2_suspeitos():
    one_suspect = [
        {"detection_mode": "baseline", "confidence": 0.9, "baseline_state_at_detection": "invalidated"},
        {"detection_mode": "baseline", "confidence": 0.9, "baseline_state_at_detection": "established"},
    ]
    assert systematic_error_evidence("asset_x", one_suspect) is False

    two_suspects = [
        {"detection_mode": "baseline", "confidence": 0.9, "baseline_state_at_detection": "invalidated"},
        {"detection_mode": "baseline", "confidence": 0.7, "baseline_state_at_detection": "learning"},
    ]
    assert systematic_error_evidence("asset_x", two_suspects) is True


def test_spectrum_confirms_por_palavra_chave():
    peaks = [{"note": "BPFO"}]
    assert spectrum_confirms("bearing_fault", peaks) is True
    assert spectrum_confirms("imbalance", peaks) is False
    assert spectrum_confirms("none", peaks) is False
