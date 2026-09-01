# Grafo Geral — Nós, LLMs, Memória e Persistência

> Descreve a estrutura interna do grafo — nodes, quais usam LLM e qual modelo, mecânica de invocação dos subgrafos — e a camada de memória/persistência (checkpointer + dumps em JSON). Para o fluxo de ponta a ponta, ver `arquitetura-geral.md`.

## Objetivo

Dar ao leitor uma visão do "mapa" do grafo — quais nodes existem, o que cada um faz, quais são LLM
e quais são código puro, e como o estado é persistido e auditável — sem detalhar a fórmula de
decisão nem a camada MCP (documentos separados).

## 1. State Schema (resumo)

O estado do grafo pai é um `TypedDict` (`SupervisorState`) com, entre outros campos: `case`
(ticket + contexto), `user_context` (populado pelo node `get_current_user`, nunca lido antes dele
rodar), `diagnostic_result` (um `DiagnosticOutput` opcional — resumo estruturado, flags de
qualidade, decisão recomendada, justificativa, evidências de suporte e ação proposta), `decision`,
`action_result`, `final_response`, e `trace`. O campo `trace` usa o reducer `operator.add` (em vez
de lista pura) porque tanto o `supervisor` quanto os dois subgrafos escrevem nesse campo em turnos
diferentes do grafo — sem reducer, cada retorno de subgrafo sobrescreveria o valor anterior em vez
de concatenar; é o mesmo padrão de `add_messages` em campos de chat, aplicado a um campo de
auditoria.

Cada subgrafo compilado (`diagnostic_subgraph`, `action_subgraph`) tem seu próprio schema interno
(ex.: `DiagnosticState` com `plan`, `collected`, `retry_count`), que **não** vaza para o
`SupervisorState` do grafo pai.

## 2. Diagrama do grafo

```
                    ┌────────────────────┐
                    │  get_current_user   │
                    └──────────┬──────────┘
                               │ user_context
                               ▼
                         ┌───────────────┐
                         │  supervisor   │◄────────────────────────┐
                         └───────┬───────┘                         │
                                 │ (primeira chamada pós-entrada)   │
                                 ▼                                  │
                   ┌─────────────────────────┐                     │
                   │  diagnostic_subgraph     │                     │
                   │  (planner→executor→      │                     │
                   │   evaluator→replanner)   │                     │
                   └─────────────┬─────────────┘                   │
                                 │ DiagnosticOutput                 │
                                 ▼                                  │
                         ┌───────────────┐                          │
                         │  supervisor   │──────────────────────────┘
                         └───┬───┬───┬───┘
             recommended_decision
              orientar│  agir │  escalar
                      ▼       ▼       ▼
           ┌───────────────┐ │ ┌──────────────────┐
           │orient_response│ │ │ escalation_node   │
           └───────┬───────┘ │ └────────┬──────────┘
                   ▼          ▼          ▼
                  END   ┌─────────────┐ END
                        │action_subgraph│
                        └──────┬───────┘
                  accepted=True│ accepted=False / 403
                        ▼             │
                       END            └──► escalation_node ──► END
```

## 3. Mecânica de invocação: subgrafo como node

`diagnostic_subgraph` e `action_subgraph` são `StateGraph` compilados de forma **independente**
(cada um com seu schema interno próprio) e registrados como **node** no grafo pai via uma função
adaptadora (`run_diagnostic_subgraph`, `run_action_subgraph`) — não são adicionados diretamente
como `graph.add_node("diagnostic_subgraph", diagnostic_subgraph)`, porque o schema interno do
subgrafo (`plan`, `collected`) não existe em `SupervisorState` e não deve vazar para o state pai. A
função adaptadora invoca o subgrafo passando só `case` e `user_context`, e devolve ao pai
`diagnostic_result`/`action_result` + o `trace` produzido (concatenado via reducer, não
sobrescrito).

Essa função de fronteira é o ponto exato onde a separação física leitura/escrita é imposta: o
adaptador do diagnóstico simplesmente não tem como devolver um `ActionResult`, e o adaptador de
ação só é chamado depois que o `supervisor` já decidiu rotear para ele — não existe caminho de
código em que `diagnostic_subgraph` chame uma tool de escrita, porque essas tools nunca são
registradas no MCP client usado dentro dele.

O roteamento do `supervisor` é feito com `Command` (não `add_conditional_edges` puro): o node
retorna diretamente o próximo destino junto com a atualização de state. A regra que decide esse
destino (`apply_decision_rule`) roda **duas vezes** no fluxo — uma dentro de `d_evaluator`, outra
no `supervisor` — como redundância proposital (ver `arquitetura-geral.md`, seção 2.5, e
`regras-de-decisao.md` para a fórmula completa).

## 4. Nós do grafo

### 4.1 Nível supervisor

| Node | Tipo | Responsabilidade |
|---|---|---|
| `get_current_user` | Código puro (chamada MCP) | Primeiro node do grafo. Chama `getCurrentUser` e popula `user_context` antes de qualquer checagem de permissão existir. Aresta única e incondicional para `supervisor`. |
| `supervisor` | Código puro (`apply_decision_rule`) | Único node com lógica de roteamento condicional real. Primeira chamada sempre despacha para `diagnostic_subgraph`. Ao receber `DiagnosticOutput`, aplica a regra de decisão e roteia para `orient_response`, `action_subgraph` ou `escalation_node`. |
| `orient_response` | **LLM — Gemini 3.5 Flash Lite** | Gera `final_response` parafraseando **apenas** `diagnostic_result.supporting_evidence` — não recebe histórico bruto de mensagens nem qualquer outra fonte de contexto no prompt. Essa restrição é o que torna o grounding verificável. |
| `escalation_node` | Código puro (chamada MCP) | Chama `escalate_case` via MCP com `justification` montada a partir de `decision_rationale`, e **sempre** formata `final_response` explicando ao cliente o motivo do escalonamento. Também é o ponto de entrada quando `action_subgraph` falha por permissão. |

### 4.2 `diagnostic_subgraph` (subgrafo compilado)

| Sub-node | Tipo | Responsabilidade |
|---|---|---|
| `d_planner` | **LLM — kimi-k3**, `structured_output` | Decide quais das 10 tools de leitura chamar e em que ordem. |
| `d_executor` | Código puro | Executa o plano via MCP, acumula respostas em `collected`, grava em `trace`. |
| `d_evaluator` | Código puro | Aplica a regra `DATA_QUALITY_OK`/`BASELINE_TRUSTWORTHY`/`SEVERITY_CRITICAL` (ver `regras-de-decisao.md`) sobre `collected`; decide se falta dado (→ `d_replanner`) ou se já pode fechar `DiagnosticOutput`. |
| `d_replanner` | **LLM — Gemini 3.7 Flash**, `structured_output` | Recebe todo o `collected` até aqui e decide um plano complementar mais específico (análogo a `d_planner`, mas replanejando em cima do que já foi observado). Só ativa em `mode in {partial, inconclusive}` com `retry_count[tool] == 0`; **não** ativa para `mode in {conflict, unavailable}` — reconsultar a mesma fonte não muda o resultado nesses dois modos. |

**Fundamentação teórica:** o ciclo `d_planner → d_executor → d_evaluator → d_replanner` é uma
instância estruturada do padrão **ReAct** (raciocínio intercalado com ação e observação) — cada
volta do loop decide a próxima tool com base na observação da chamada anterior (`mode`, `notes`,
dado retornado), em vez de um plano fixo decidido de uma vez só. A diferença para o ReAct
"genérico" é que o passo de decidir **se** falta dado e **por quê** (`d_evaluator`) é código
determinístico, não chamada de LLM — o que faz o `mode` do `QueryEnvelope` ser checado de forma
confiável, sem depender do modelo "lembrar" de olhar o campo (ver `camada-mcp-e-erros.md`). Só o
passo seguinte, de decidir **qual** tool complementar buscar dado o que já foi observado
(`d_replanner`), é LLM.

`diagnostic_subgraph` retorna `DiagnosticOutput` para o `supervisor` — o supervisor nunca vê `mode`
bruto, só a conclusão já resolvida.

### 4.3 `action_subgraph` (subgrafo compilado)

| Sub-node | Tipo | Responsabilidade |
|---|---|---|
| `a_permission_check` | Código puro | Revalida `PERM_OK(proposed_action)` contra `user_context.permissions` **antes** de chamar a API — segunda barreira, além do 403 que a própria API já retornaria. Se falhar, retorna direto para `supervisor` com flag de erro (roteia para `escalation_node`). |
| `a_justify` | Código puro | Monta o texto de `justification` (≥ 20 caracteres) a partir de `decision_rationale` + `supporting_evidence` do diagnóstico — nunca texto livre do LLM sem referência ao diagnóstico. |
| `a_execute` | Código puro (chamada MCP) | Chama a tool de ação via MCP (`update_asset_config`, `reprocess_analysis`, `request_specialist_analysis` ou `request_retraining`). Grava `ActionResult` em `action_result` e em `trace`. |

Nenhum sub-node de `action_subgraph` é LLM — a montagem da justificativa é determinística, ancorada
no que o diagnóstico já produziu.

## 5. Memória e persistência

### 5.1 Checkpointer (memória de execução em andamento)

- Checkpointer no grafo pai: `SqliteSaver` para desenvolvimento local (trocar por `PostgresSaver`
  se precisar de concorrência/multi-processo). `thread_id = case_id`.
- Subgrafos compilados herdam o checkpointer do pai automaticamente ao serem invocados como node —
  não precisa de storage duplicado por subgrafo.
- **Memória entre casos** (ex.: "este ativo já foi escalado 3x este mês") não é coberta pelo
  checkpointer por thread — exigiria um `Store` do LangGraph (key-value cross-thread, chaveado por
  `asset_id` ou `company_id`). Está **fora do escopo** desta versão da arquitetura; é uma extensão a
  avaliar separadamente se o caso de uso exigir contexto histórico entre tickets.

### 5.2 Persistência de output em JSON (toda execução do agente)

Além do checkpointer (que serve o próprio grafo, para retomar/depurar uma thread em andamento),
**toda** invocação completa do agente — teste manual ou execução do harness de avaliação — grava
registros em `data/jsons-agents/`, fora do checkpointer, como registro bruto legível e versionável.
Há dois níveis de granularidade, ambos escritos pela mesma execução:

**Um JSON por chamada de LLM (pasta dedicada por node)**

Cada node que faz chamada de LLM (`d_planner`, `d_replanner`, `orient_response`) grava sua própria
saída estruturada, isolada num JSON próprio, na sua subpasta dedicada:

- Pastas: `data/jsons-agents/d_planner/`, `data/jsons-agents/d_replanner/`,
  `data/jsons-agents/orient_response/` — uma por node LLM.
- Nomenclatura: `<seq>__<case_id>__seed-<seed>__call-<n>__<timestamp>.json`, onde `<seq>` é contado
  dentro da subpasta do node e `<n>` é o índice da chamada daquele node dentro da mesma execução
  (relevante para `d_replanner`, que pode rodar mais de uma vez por caso; sempre `call-1` para
  `d_planner` e `orient_response`, que rodam no máximo uma vez por execução). Exemplo:
  `data/jsons-agents/d_replanner/0003__case_0042__seed-none__call-1__20260830T211500.json`.
- Conteúdo: a saída estruturada específica daquele node — `d_planner`: o plano inicial
  (`list[tool_name]`); `d_replanner`: o `collected` recebido como entrada + o plano complementar
  decidido; `orient_response`: o `final_response` gerado + os itens de `supporting_evidence` que o
  originaram.
- Quem escreve: uma função utilitária compartilhada (`dump_llm_output(node_name, payload, case_id,
  seed)`), chamada pelos três nodes logo após a resposta do LLM — evita reimplementar a lógica de
  nomenclatura/serialização em cada node.

**Um JSON final por execução (`SupervisorState` completo)**

Ao fim de cada execução completa do grafo, grava o `SupervisorState` final como um único arquivo
JSON diretamente em `data/jsons-agents/` (fora das subpastas por node) — a visão agregada de tudo
que os agentes produziram naquele caso:

- Nomenclatura: `data/jsons-agents/<seq>__<case_id>__seed-<seed>__<timestamp>.json`, onde `<seq>` é
  um índice sequencial zero-padded (calculado contando os arquivos já existentes na pasta),
  `<case_id>` é o `case_id` do ticket (execução ad-hoc) ou o `scenario_id` (`CEN-01`, ...) quando a
  execução vem do harness, `seed-<seed>` é o valor de seed usado (ou `seed-none`), e `<timestamp>` é
  `YYYYMMDDTHHMMSS` de quando a execução terminou. Exemplo:
  `data/jsons-agents/0007__CEN-03__seed-a1__20260830T211500.json`.
- Conteúdo: o `SupervisorState` completo serializado (`case`, `user_context`, `diagnostic_result`,
  `decision`, `action_result`, `final_response`, `trace`) — o mesmo dado que o runner do harness e a
  camada determinística/juiz consomem, sem transformação adicional. Já embute, agregado, o resultado
  de cada JSON por node; os dumps por node existem para inspecionar uma chamada de LLM isolada, este
  é o que os scripts de avaliação de fato leem.
- Por que fora do checkpointer: o `SqliteSaver`/`PostgresSaver` guarda checkpoints internos do
  LangGraph, no formato interno do framework — não é o formato pensado para leitura humana nem para
  ser consumido por `eval/report.py`. O dump em `data/jsons-agents/` é a fonte de dado bruto,
  estável e legível, independente de trocar de checkpointer ou de versão do LangGraph.
- Quem escreve: um único ponto de código (um adaptador fino em torno de
  `supervisor_graph.invoke(...)`), chamado tanto pelo runner manual quanto por `eval/runner.py` —
  evita duplicar a lógica de nomenclatura/serialização em dois lugares. Independente do ponto de
  escrita do dump por node — um não substitui o outro.

## Integrações

- **`arquitetura-geral.md`** — mostra como esses nodes se encadeiam no fluxo completo, do ponto de
  vista do que acontece com um ticket, não da estrutura interna do grafo.
- **`regras-de-decisao.md`** — detalha a fórmula que `d_evaluator` e `supervisor` aplicam
  (mencionada aqui só como responsabilidade dos nodes).
- **`camada-mcp-e-erros.md`** — detalha como `d_executor` e `a_execute` chamam as tools via MCP e
  tratam erro/`mode`.
- **`metodologia-avaliacao.md`** — os dumps em JSON descritos na seção 5.2 são exatamente o que o
  runner de avaliação lê (sem re-executar o agente) para aplicar as camadas determinística e de
  juiz.
