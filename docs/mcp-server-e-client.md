# `client.py` e `agent/mcp_server.py` — como funcionam

> Camada de integração do agente com a API industrial Tractian.

## 1. Por que dois arquivos separados

- **`client.py`** (raiz do repo) — cliente HTTP puro. Não sabe o que é MCP, LLM ou tool-calling;
  só sabe conversar com a API Tractian (`docs/api-contract.openapi.yaml`). Pode ser reusado por
  qualquer coisa que precise falar com a API: o servidor MCP, um script de avaliação, um teste.
- **`agent/mcp_server.py`** — expõe cada método do `client.py` como uma **tool MCP**, para um
  agente (LangGraph, Claude, qualquer host MCP) descobrir e chamar.

Separar assim significa que trocar de framework de orquestração (LangChain → LangGraph → outro
MCP host) nunca exige tocar em `client.py` — só a camada de exposição muda.

## 2. `client.py`

### `TractianAPIError`

Exceção lançada quando a API responde `4xx`/`5xx`. Carrega os três campos do schema `Error` do
contrato:

```python
class TractianAPIError(Exception):
    def __init__(self, status_code: int, code: str, message: str): ...
```

### `TractianClient`

Um método por `operationId` do contrato — 18 no total, agrupados nas mesmas 7 categorias do
`STUDENT-GUIDE.md` (Contexto, Ativos, Análises, Dados técnicos, Modelos, Conhecimento, Ações).

Por baixo, três helpers privados fazem o trabalho repetido:

| Helper | Usado por | O que faz |
| :--- | :--- | :--- |
| `_get(path, user_id=None, seed=None, **params)` | os 13 GETs de consulta | monta a query string (filtra `None`), injeta `x-user-id` se fornecido, chama `_handle_response` |
| `_post(path, user_id, justification, params=None)` | `reprocess_analysis`, `request_specialist_analysis`, `request_retraining`, `escalate_case` | monta o corpo `{justification, params}` do schema `ActionRequest` |
| `_patch(path, user_id, justification, **extra)` | `update_asset_config` | igual ao `_post`, mas aceita campos extras no corpo (`changes`) |

`_handle_response` é o único lugar que decide sucesso vs. erro: se `status_code >= 400`, tenta
ler `{code, message}` do corpo (schema `Error`) e levanta `TractianAPIError`; senão, devolve o
JSON decodificado.

**Decisão de design — `user_id` é parâmetro explícito, não injetado internamente.** Cada `case`
de `agent-input/cases.json` já vem com um `user_id` fixo (contexto de quem abriu o chamado). O
cliente não adivinha nem fixa esse valor sozinho — quem orquestra o agente decide e passa
explicitamente, o que mantém o contexto de permissão visível e auditável em cada chamada do
trace.

### Configuração

`API_BASE_URL` lê a env var `TRACTIAN_API_URL`, com fallback para `http://localhost:8000`
(mesma porta usada por `make up`).

## 3. `agent/mcp_server.py`

### Estrutura

```python
mcp = FastMCP("tractian-industrial-api")
client = TractianClient()

@mcp.tool()
def get_asset(asset_id: str, seed: str | None = None) -> dict:
    """docstring vira a descrição da tool para o LLM"""
    return _call(client.get_asset, asset_id, seed=seed)
```

Cada uma das 18 tools é uma função fininha: recebe os mesmos parâmetros do método correspondente
em `TractianClient`, chama-o via `_call`, e devolve o resultado. O nome da tool, os parâmetros e
o docstring viram automaticamente o schema JSON que o LLM enxerga (via `FastMCP`, que introspecta
type hints + docstring).

### `_call` — de exceção a dado observável

```python
def _call(fn, *args, **kwargs) -> dict:
    try:
        return fn(*args, **kwargs)
    except TractianAPIError as e:
        return {"error": {"code": e.code, "message": e.message, "status_code": e.status_code}}
```

Toda tool passa por aqui. Em vez de deixar `TractianAPIError` estourar como exceção não tratada
(o que interromperia o loop do agente), o erro vira um dict igual a qualquer outro retorno —
o agente recebe a falha como **observação** e decide o próximo passo (ex.: um `403` em
`escalate_case` pode levar o agente a tentar outra ação, ou reportar que não tem permissão, em
vez de a execução simplesmente quebrar).

### As 18 tools, por categoria

| Categoria | Tools (consulta) | Tools (ação) |
| :--- | :--- | :--- |
| Contexto | `get_company`, `list_assets_by_company`, `get_current_user` | — |
| Ativos | `get_asset` | `update_asset_config` |
| Análises | `list_analyses`, `get_analysis` | `reprocess_analysis`, `request_specialist_analysis` |
| Dados técnicos | `get_baseline`, `get_rms_series`, `get_spectrum`, `get_data_quality` | — |
| Modelos | `get_model` | `request_retraining` |
| Conhecimento | `search_knowledge`, `get_knowledge_doc` | — |
| Ações/Escalonamento | — | `escalate_case` |

Tools de ação sempre exigem `user_id` + `justification` (≥ 20 caracteres, validado pela própria
API) — refletindo o requisito do contrato para operações de alto impacto.

### Import de `client.py` a partir de `agent/`

`mcp_server.py` vive em `agent/`, mas `client.py` vive na raiz do repo. Para importar sem exigir
instalar o projeto como pacote, o arquivo insere a raiz no `sys.path` antes do import:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from client import TractianAPIError, TractianClient
```

Isso deixa `python agent/mcp_server.py` funcionando de qualquer diretório de trabalho.

### Rodando

```bash
source .venv/bin/activate        # .venv criado com `uv venv --python 3.12` na raiz do repo
python agent/mcp_server.py       # sobe o servidor MCP (stdio) — mcp.run()
```

Pré-requisito: a API precisa estar no ar (`make up`, porta `:8000`).

## 4. Por que `mcp<2` em `requirements.txt`

O SDK `mcp` lançou uma versão 2.x que renomeou `FastMCP` para `MCPServer`, com API diferente. O
código aqui usa o padrão `FastMCP` (`from mcp.server.fastmcp import FastMCP`), que é o mais
documentado e estável em tutoriais/exemplos da comunidade. `requirements.txt` fixa
`mcp>=1.2,<2` para não quebrar com a v2 sem uma migração deliberada.

## 5. Ambiente local

O `mcp` SDK exige Python ≥ 3.10. Como só havia Python 3.9 disponível na máquina, o ambiente foi
criado com [`uv`](https://docs.astral.sh/uv/) (a ferramenta já sugerida no `STUDENT-GUIDE.md`),
que baixa e gerencia sua própria versão de Python:

```bash
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## 6. Testado contra a API real

Ambos os arquivos foram validados com a API rodando (`make up`), não só por import estático:
`get_asset`, `get_current_user`, `get_baseline`, `get_model` chamados de ponta a ponta, e o
tratamento de erro conferido chamando `escalate_case` com um `case_id` inexistente (retornou
`{"error": {"code": "NOT_FOUND", ...}}` em vez de estourar exceção). O caso de `get_asset` expôs
uma implementação incompleta na própria API (`GET /assets/{assetId}` não aninhava
`hierarchy`/`config` como o contrato já documentava) — corrigido em `api/app/main.py` e registrado
em `alteracoes-ymal.md` (item 5). `client.py`/`mcp_server.py` não precisaram de nenhuma mudança
por causa disso: tratam `data` como dict opaco, sem presumir formato interno.
