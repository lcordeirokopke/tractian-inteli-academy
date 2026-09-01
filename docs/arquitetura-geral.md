# Arquitetura Geral — Visão de Fluxo Fim a Fim

> Documento descreve o fluxo
> completo de execução do agente, do recebimento do ticket até a validação da resposta final, sem
> entrar no detalhe interno de cada subgrafo (ver `grafo-e-nos.md`), da regra de decisão (ver
> `regras-de-decisao.md`) ou da camada MCP (ver `camada-mcp-e-erros.md`).

## Objetivo

Explicar, em um único lugar, o caminho que um ticket percorre desde a entrada no sistema até a
geração e o embasamento (grounding) da resposta final — sem exigir que o leitor conheça todos os
outros documentos para entender o desenho geral.

## 1. Visão geral da arquitetura

O agente é um **supervisor multi-agente com subgrafos fisicamente separados** por responsabilidade:
diagnóstico (leitura) vs. ação (escrita). O grafo é orquestrado por um node `supervisor`, que nunca
executa lógica de negócio diretamente — só decide para onde rotear com base no que os subgrafos
devolvem.

- **`diagnostic_subgraph`** — acesso só às tools **somente-leitura** da API (10 das 13 de leitura:
  `getAsset`, `getBaseline`, `getRmsSeries`, `getSpectrum`, `getDataQuality`, `listAnalyses`,
  `getAnalysis`, `getModel`, `searchKnowledge`, `getKnowledgeDoc`). Investiga o caso e devolve uma
  recomendação estruturada — **nunca** escreve na API. Ficam de fora do escopo do diagnóstico,
  deliberadamente: `getCompany` e `listAssetsByCompany` (o ticket já chega com
  `company_id`/`asset_id` resolvidos via `agent-input/cases.json`) e `getCurrentUser`, que não é
  tool opcional do planner, mas pré-requisito de fluxo resolvido por um node dedicado antes de
  qualquer outra coisa no grafo.
- **`action_subgraph`** — único ponto do sistema com acesso às **5 tools de impacto**
  (`updateAssetConfig`, `reprocessAnalysis`, `requestSpecialistAnalysis`, `requestRetraining`,
  `escalateCase`). Só é acionado quando o diagnóstico recomenda agir ou escalar.

**Por que separar fisicamente:** isola o "raio de explosão" de uma decisão errada. Um bug ou
alucinação no raciocínio de diagnóstico nunca tem, por construção, acesso às tools que escrevem na
API — para isso, o `supervisor` precisa primeiro aceitar a recomendação e rotear explicitamente
para `action_subgraph`. Essa é a hipótese de segurança que essa opção de arquitetura testa em
relação a alternativas de grafo único. O isolamento também facilita testar `action_subgraph`
sozinho, com `diagnostic_result` mockado, sem depender do LLM de diagnóstico rodar corretamente
primeiro — algo relevante para o experimento de avaliação (ver `metodologia-avaliacao.md`).

## 2. Fluxo passo a passo, do início à validação da resposta

### 2.1 Entrada

O runner (fora do grafo) carrega o item de `agent-input/cases.json`, monta o estado inicial
(`SupervisorState{case, trace: []}`) e invoca o grafo com `thread_id = case_id`. Existem dois
pontos de entrada possíveis para disparar essa invocação — **modo manual** (informar `case_id` e,
opcionalmente, `seed`/`user_id`) e **modo runner/harness** (itera os 16 cenários × seeds fixos de
`eval/config.yaml`, sem input humano em tempo de execução). Ambos convergem para o mesmo adaptador
`run_case(case_id, seed=None, user_id=None)`; a estrutura do grafo (nodes, roteamento, regra de
decisão) é idêntica nos dois modos — o que muda é só como `case_id`/`seed`/`user_id` chegam até
`run_case`. Mesmo `case_id` + mesmo `seed` produz a mesma trajetória em qualquer um dos dois modos.

### 2.2 Resolução de identidade — `get_current_user`

Primeiro node do grafo, com aresta única e incondicional para `supervisor`. Chama `getCurrentUser`
(o `x-user-id` já vai no header da sessão MCP) e popula `user_context` (role, permissions) **antes**
de qualquer checagem de permissão existir no restante do fluxo. Essa chamada é registrada em
`trace` como qualquer outro node.

### 2.3 Primeiro despacho do supervisor

Com `diagnostic_result` ainda `None`, o `supervisor` sempre despacha para `diagnostic_subgraph` —
não há lógica condicional nessa primeira passagem.

### 2.4 Diagnóstico

Dentro de `diagnostic_subgraph`, um ciclo do tipo ReAct (planejar → executar → avaliar →
replanejar) coleta dados via MCP, avalia sua qualidade/confiabilidade e monta um `DiagnosticOutput`
estruturado: resumo da análise, flags de qualidade, decisão recomendada
(`orientar`/`agir`/`escalar`), justificativa ancorada em evidência, e (se aplicável) a ação
proposta. O detalhamento de cada sub-node e dos modelos usados está em `grafo-e-nos.md`; a lógica
que decide `orientar`/`agir`/`escalar` está em `regras-de-decisao.md`.

### 2.5 Segundo despacho do supervisor

Com `diagnostic_result` presente, o `supervisor` revalida a regra de decisão (seção 5 do plano —
ver `regras-de-decisao.md`) sobre o `DiagnosticOutput` já resumido, e roteia:

- `orientar` → `orient_response` → `END`
- `agir` → `action_subgraph`
- `escalar` → `escalation_node` → `END`

Essa revalidação é redundância proposital: `d_evaluator` (dentro do diagnóstico) decide com base
nos dados brutos coletados, e o `supervisor` reaplica a mesma regra sobre o resultado já resumido
antes de liberar `action_subgraph`. Se as duas divergirem (bug de serialização, campo perdido na
transição), o `supervisor` tem precedência e o caso vai para `escalation_node` por segurança —
nunca o inverso.

### 2.6 Geração da resposta ao cliente (caminho `orientar`)

`orient_response` é uma chamada de LLM restrita a parafrasear **apenas**
`diagnostic_result.supporting_evidence` — não recebe histórico bruto de mensagens nem qualquer
outra fonte de contexto no prompt. Essa ausência deliberada de outras fontes é o que torna o
grounding verificável (seção 4 abaixo).

### 2.7 Ação (caminho `agir`)

Dentro de `action_subgraph`: revalidação de permissão (`a_permission_check`, segunda barreira além
do 403 que a API já retornaria), montagem de justificativa ancorada em evidência (`a_justify`,
nunca texto livre sem referência ao diagnóstico) e execução da tool de ação via MCP (`a_execute`).
Se a permissão falhar, o subgrafo retorna ao `supervisor` com uma flag de erro em vez de
`action_result`, e o caso é reclassificado para `escalar`.

### 2.8 Escalonamento (caminho `escalar`, direto ou por falha de permissão)

`escalation_node` chama `escalate_case` via MCP com uma `justification` montada a partir de
`decision_rationale` e **sempre** formata `final_response` explicando ao cliente o motivo do
escalonamento — inclusive quando o escalonamento veio de uma falha de permissão em
`action_subgraph` (nesse caso, a justificativa explica que a ação recomendada exigia uma permissão
que o usuário atual não possui). Nenhum node terminal deixa o cliente sem resposta.

### 2.9 Encerramento

Todo node terminal (`orient_response`, `escalation_node`, e o `END` após `action_subgraph`
aceito/`accepted=True`) grava `final_response`. Se `action_subgraph` retornar
`accepted=False`/`403`, o fluxo passa por `escalation_node` antes de encerrar.

## 3. Exemplo ilustrativo (resumo)

Ticket "vibração alta no motor principal" (`asset_id=asset_M101`, usuário `role=mechanic`,
`permissions=[read, action_low]`): `get_current_user` resolve o contexto → `d_planner` decide um
plano inicial de 5 tools de leitura → `get_rms_series` volta `mode=partial` → `d_evaluator` não
fecha ainda, roteia para `d_replanner` → `d_replanner` decide `get_spectrum` como complementar →
espectro confirma o sintoma (pico BPFO) → `d_evaluator` fecha com `recommended_decision="agir"`,
`proposed_action="request_specialist_analysis"` → `supervisor` revalida e roteia para
`action_subgraph` → `a_permission_check` aprova (`action_low` presente) → `a_justify` monta a
justificativa → `a_execute` chama a API, que responde `accepted=true` → `END`, com `final_response`
citando exatamente os itens de `supporting_evidence`. O passo a passo completo, incluindo caminhos
alternativos (severidade crítica, falha de permissão, dado insuficiente mesmo após replanejamento),
está em `plano-arquitetura.md` §3.4.

## 4. Rastreabilidade e fundamentação

- **Phoenix** (`arize-phoenix`, open-source, self-hosted) é a camada de observabilidade/tracing.
  `px.launch_app()` sobe a UI localmente (in-process, sem Docker/servidor separado); o
  instrumentador `openinference-instrumentation-langchain`
  (`LangChainInstrumentor().instrument()`) captura automaticamente a mesma hierarquia que um APM de
  LLM daria: `supervisor` como span pai, `diagnostic_subgraph` e `action_subgraph` como spans
  filhos, cada sub-node aninhado dentro deles — sem instrumentação manual além dessa chamada de
  setup.
- **Por que Phoenix em vez de um serviço gerenciado (ex.: LangSmith):** a avaliação roda os 16
  cenários × ≥ 3 seeds repetidamente para calibrar thresholds — volume de trace alto o suficiente
  para esbarrar em teto de tier gratuito de um SaaS. Rodando local/self-hosted, não há teto de
  volume nem dependência de conta externa, e o dado (mesmo sendo sintético) não sai da máquina.
- `trace` (campo do state, com reducer `operator.add`) continua sendo o rastro estruturado usado
  pela avaliação para comparar contra `eval/expected-paths.json` — cada entrada tem `{node, tool,
  args, result_summary, ts}`, suficiente para reconstruir chamadas, justificativas e decisão sem
  depender do Phoenix estar no ar. Phoenix é observabilidade/depuração complementar (útil para
  inspecionar visualmente uma execução específica), mas não é a fonte de verdade que os scripts de
  avaliação leem.
- **Grounding estrutural:** `orient_response` e `a_justify` só têm acesso a
  `diagnostic_result.supporting_evidence` (lista tipada, não texto livre) — dá para validar
  programaticamente, como parte do runner de avaliação, que toda resposta final e toda
  `justification` referenciam pelo menos um item de `supporting_evidence` realmente presente na
  resposta da API (não inventado pelo LLM). Essa mesma garantia é auditada qualitativamente pelo
  `grounding_score` (GEval) descrito em `metodologia-avaliacao.md`.

## 5. Limitações conhecidas desta arquitetura

- **Overhead de orquestração maior que as opções de grafo único** — mais latência por caso, não por
  chamada de LLM no `supervisor` (que é `apply_decision_rule`, código puro), mas pelas idas e vindas
  extras entre `get_current_user` → `supervisor` → `diagnostic_subgraph` → `supervisor` →
  `action_subgraph`/`orient_response`, somadas à(s) chamada(s) de LLM dentro do subgrafo de
  diagnóstico. Relevante se o volume de casos for alto.
- **Separação leitura/escrita não elimina risco de decisão errada**, só o risco de uma tool de
  escrita ser chamada **sem** passar pela decisão do supervisor — erro de julgamento dentro do
  diagnóstico (ex.: `recommended_decision` errado) ainda propaga normalmente.
- **Memória entre casos não está implementada nesta versão** — se o "contexto entre interações"
  exigido pelo enunciado incluir histórico entre tickets do mesmo ativo (ex.: "este ativo já foi
  escalado 3x este mês"), precisa de extensão explícita via `Store` do LangGraph (key-value
  cross-thread). Ver detalhe em `grafo-e-nos.md`, seção de memória e persistência.

## Integrações

- **`grafo-e-nos.md`** — detalha os nós internos de cada subgrafo, os modelos de LLM usados em cada
  um, e a persistência de estado/JSONs que sustenta a rastreabilidade descrita na seção 4 acima.
- **`regras-de-decisao.md`** — detalha a regra `orientar`/`agir`/`escalar` aplicada em `d_evaluator`
  e revalidada no `supervisor` (seções 2.4 e 2.5 acima).
- **`camada-mcp-e-erros.md`** — detalha como as chamadas às tools da API (usadas em todos os passos
  de 2.4 a 2.8) tratam erro e como o campo `mode` das respostas alimenta o replanejamento.
- **`metodologia-avaliacao.md`** — detalha como o `trace` e o `SupervisorState` final produzidos por
  este fluxo são consumidos pela camada de avaliação (determinística + juiz por LLM).