"""Sessões e toolsets MCP separados (leitura-diagnóstico vs ação) — Estágio 3 do plano de execução
Fase 2.

`diagnostic_subgraph` só enxerga `DIAGNOSTIC_READ_TOOLS` (nunca uma tool de escrita — ver
camada-mcp-e-erros.md §3); `action_subgraph` só enxerga `ACTION_TOOLS`. `escalate_case` fica de fora
das duas listas — é exclusiva de `escalation_node` (nível pai).

`mcp_session` abre uma sessão MCP stdio contra `agent/mcp_server.py` (já implementado, não mexer) e
vincula `user_id`/`seed` a cada tool no momento da invocação: os wrappers devolvidos por
`get_diagnostic_tools()`/`get_action_tools()` já têm esses dois parâmetros pré-preenchidos e
removidos do schema exposto ao LLM — nenhum node/LLM precisa (nem consegue) informá-los na chamada
da tool, e não é necessário nenhum campo extra em SupervisorState/DiagnosticState/ActionState para
isso.
"""

import contextvars
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_SERVER_PATH = str(Path(__file__).resolve().parent / "mcp_server.py")

DIAGNOSTIC_READ_TOOLS = [
    "get_asset",
    "get_baseline",
    "get_rms_series",
    "get_spectrum",
    "get_data_quality",
    "list_analyses",
    "get_analysis",
    "get_model",
    "search_knowledge",
    "get_knowledge_doc",
]
ACTION_TOOLS = [
    "update_asset_config",
    "reprocess_analysis",
    "request_specialist_analysis",
    "request_retraining",
]  # escalate_case NÃO entra aqui — exclusivo de escalation_node

_current_tools: contextvars.ContextVar[dict[str, BaseTool] | None] = contextvars.ContextVar(
    "_current_tools", default=None
)


def _server_connection() -> dict[str, Any]:
    return {
        "tractian": {
            "command": sys.executable,
            "args": [MCP_SERVER_PATH],
            "transport": "stdio",
        }
    }


def _bind_context(tool: BaseTool, user_id: str, seed: str | None) -> BaseTool:
    """Devolve uma cópia do tool MCP com `user_id`/`seed` pré-preenchidos e removidos do JSON
    Schema exposto ao LLM (`tool.args_schema`, aqui um dict — `load_mcp_tools` gera o schema direto
    do `inputSchema` MCP, sem passar por um `BaseModel` pydantic). Só mexe nos campos que a tool de
    fato declara (nem toda tool tem `user_id`, nem toda tool tem `seed`) — as demais tools voltam
    inalteradas."""
    schema = tool.args_schema if isinstance(tool.args_schema, dict) else {}
    properties = schema.get("properties", {})
    fixed: dict[str, Any] = {}
    if "user_id" in properties:
        fixed["user_id"] = user_id
    if "seed" in properties:
        fixed["seed"] = seed
    if not fixed:
        return tool

    bound_schema = {
        **schema,
        "properties": {name: spec for name, spec in properties.items() if name not in fixed},
        "required": [name for name in schema.get("required", []) if name not in fixed],
    }

    async def _bound_coroutine(**kwargs: Any) -> Any:
        return await tool.coroutine(**kwargs, **fixed)

    return StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=bound_schema,
        coroutine=_bound_coroutine,
        handle_tool_error=tool.handle_tool_error,
    )


@asynccontextmanager
async def mcp_session(user_id: str, seed: str | None = None):
    """Abre uma sessão MCP (stdio) contra `agent/mcp_server.py` e disponibiliza, via contextvar, os
    toolsets já vinculados a `user_id`/`seed` — válido durante o bloco `async with`. `run_case`
    (Estágio 9) é quem abre essa sessão; todo node chamado dentro dela usa `get_diagnostic_tools()`/
    `get_action_tools()` para pegar as tools já prontas."""
    client = MultiServerMCPClient(_server_connection())
    raw_tools = await client.get_tools()
    bound = {tool.name: _bind_context(tool, user_id, seed) for tool in raw_tools}
    token = _current_tools.set(bound)
    try:
        yield bound
    finally:
        _current_tools.reset(token)


def _require_tools() -> dict[str, BaseTool]:
    tools = _current_tools.get()
    if tools is None:
        raise RuntimeError(
            "Nenhuma sessão MCP ativa — chame get_diagnostic_tools()/get_action_tools() dentro de "
            "um bloco `async with mcp_session(user_id, seed):`."
        )
    return tools


def get_diagnostic_tools() -> list[BaseTool]:
    tools = _require_tools()
    return [tools[name] for name in DIAGNOSTIC_READ_TOOLS if name in tools]


def get_action_tools() -> list[BaseTool]:
    tools = _require_tools()
    return [tools[name] for name in ACTION_TOOLS if name in tools]
