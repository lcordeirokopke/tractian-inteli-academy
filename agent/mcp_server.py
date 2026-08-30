"""Servidor MCP que expõe a API industrial Tractian como tools.

Uma tool por operationId do contrato (`docs/api-contract.openapi.yaml`), agrupadas em consulta
(GET, retornam o envelope {mode, notes, data} sem achatar) e ação (POST/PATCH de impacto, exigem
justification e user_id). Erros HTTP viram um dict {"error": {...}} em vez de exceção, para o
agente enxergar a falha como observação e decidir o próximo passo.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client import TractianAPIError, TractianClient  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("tractian-industrial-api")
client = TractianClient()


def _call(fn: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return fn(*args, **kwargs)
    except TractianAPIError as e:
        return {"error": {"code": e.code, "message": e.message, "status_code": e.status_code}}


# -- Contexto -----------------------------------------------------------


@mcp.tool()
def get_company(company_id: str, seed: str | None = None) -> dict:
    """Consulta dados de uma empresa (nome, segmento, timezone)."""
    return _call(client.get_company, company_id, seed=seed)


@mcp.tool()
def list_assets_by_company(company_id: str, seed: str | None = None) -> dict:
    """Lista os ativos de uma empresa."""
    return _call(client.list_assets_by_company, company_id, seed=seed)


@mcp.tool()
def get_current_user(user_id: str) -> dict:
    """Consulta perfil e permissões da pessoa usuária (role, permissions, company_id)."""
    return _call(client.get_current_user, user_id)


# -- Ativos ---------------------------------------------------------------


@mcp.tool()
def get_asset(asset_id: str, seed: str | None = None) -> dict:
    """Consulta um ativo: criticidade, hierarquia, pontos de sensor e configuração técnica."""
    return _call(client.get_asset, asset_id, seed=seed)


@mcp.tool()
def update_asset_config(asset_id: str, user_id: str, justification: str, changes: dict) -> dict:
    """Altera criticidade e/ou configuração técnica de um ativo. Ação de impacto: exige
    justification (>= 20 caracteres) e permissão action_high. `changes` aceita as chaves
    `criticality` e/ou `config` (machine_type, rotation_rpm, bearing_specs, line_frequency_hz)."""
    return _call(client.update_asset_config, asset_id, user_id=user_id, justification=justification, changes=changes)


# -- Análises -------------------------------------------------------------


@mcp.tool()
def list_analyses(asset_id: str, status: str | None = None, seed: str | None = None) -> dict:
    """Lista análises (insights) de um ativo. `status` filtra por current/stale/pending/inconclusive."""
    return _call(client.list_analyses, asset_id, status=status, seed=seed)


@mcp.tool()
def get_analysis(analysis_id: str, seed: str | None = None) -> dict:
    """Detalhe de uma análise: tipo, severidade, confiança, evidências, limitações, modo de detecção."""
    return _call(client.get_analysis, analysis_id, seed=seed)


@mcp.tool()
def reprocess_analysis(analysis_id: str, user_id: str, justification: str, params: dict | None = None) -> dict:
    """Solicita reprocessamento de uma análise. Ação de impacto: exige justification (>= 20 caracteres)."""
    return _call(client.reprocess_analysis, analysis_id, user_id=user_id, justification=justification, params=params)


@mcp.tool()
def request_specialist_analysis(
    analysis_id: str, user_id: str, justification: str, params: dict | None = None
) -> dict:
    """Solicita análise especializada humana sobre uma análise automática. Ação de impacto:
    exige justification (>= 20 caracteres)."""
    return _call(
        client.request_specialist_analysis,
        analysis_id,
        user_id=user_id,
        justification=justification,
        params=params,
    )


# -- Dados técnicos ---------------------------------------------------------------


@mcp.tool()
def get_baseline(asset_id: str, point_id: str | None = None, seed: str | None = None) -> dict:
    """Consulta o baseline (estado normal aprendido) de um ativo/ponto: state (learning/
    established/invalidated), detection_mode (baseline/symptom) e features de referência."""
    return _call(client.get_baseline, asset_id, point_id=point_id, seed=seed)


@mcp.tool()
def get_rms_series(asset_id: str, point_id: str | None = None, seed: str | None = None) -> dict:
    """Consulta a série temporal de RMS de vibração de um ativo/ponto, com referência de
    baseline e limiar de alarme."""
    return _call(client.get_rms_series, asset_id, point_id=point_id, seed=seed)


@mcp.tool()
def get_spectrum(asset_id: str, point_id: str | None = None, seed: str | None = None) -> dict:
    """Consulta o espectro FFT (picos de frequência) de um ativo/ponto."""
    return _call(client.get_spectrum, asset_id, point_id=point_id, seed=seed)


@mcp.tool()
def get_data_quality(asset_id: str, seed: str | None = None) -> dict:
    """Consulta completude, SNR e frescor dos dados de um ativo — usar antes de confiar em um
    insight ou baseline."""
    return _call(client.get_data_quality, asset_id, seed=seed)


# -- Modelos ---------------------------------------------------------------


@mcp.tool()
def get_model(model_id: str, seed: str | None = None) -> dict:
    """Consulta um modelo de diagnóstico: versão, cobertura por machine_type, requisitos mínimos
    (completude, SNR, RPM) e estado de processamento."""
    return _call(client.get_model, model_id, seed=seed)


@mcp.tool()
def request_retraining(model_id: str, user_id: str, justification: str, params: dict | None = None) -> dict:
    """Solicita retreinamento de um modelo. Ação de alto impacto: exige justification forte
    (>= 20 caracteres)."""
    return _call(client.request_retraining, model_id, user_id=user_id, justification=justification, params=params)


# -- Conhecimento ---------------------------------------------------------------


@mcp.tool()
def search_knowledge(q: str, type: str | None = None, seed: str | None = None) -> dict:
    """Busca documentos de conhecimento (procedimentos, glossário, orientações) por texto livre."""
    return _call(client.search_knowledge, q, type=type, seed=seed)


@mcp.tool()
def get_knowledge_doc(doc_id: str, seed: str | None = None) -> dict:
    """Consulta um documento de conhecimento pelo ID."""
    return _call(client.get_knowledge_doc, doc_id, seed=seed)


# -- Ações / Escalonamento ---------------------------------------------------------------


@mcp.tool()
def escalate_case(case_id: str, user_id: str, justification: str, params: dict | None = None) -> dict:
    """Encaminha o caso para análise humana. Ação de impacto: exige justification (>= 20
    caracteres). Usar quando o caso extrapola o atendimento remoto."""
    return _call(client.escalate_case, case_id, user_id=user_id, justification=justification, params=params)


if __name__ == "__main__":
    mcp.run()
