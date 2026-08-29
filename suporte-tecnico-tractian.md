# Arquitetura de Suporte Técnico e Processo de Solicitação de Atendimento na Tractian

A gestão da confiabilidade na indústria moderna exige que hardwares de sensoriamento de condição e softwares de gestão da manutenção operem em perfeita sintonia e sem interrupções. No ecossistema da Tractian, composto por sensores de monitoramento online (Smart Trac Pro, Smart Trac Ex e Energy Trac), receptores de dados (Smart Receiver) e o software de gestão (Tractian CMMS), a infraestrutura de suporte técnico é projetada para assegurar a continuidade operacional e a resolução rápida de divergências físicas ou digitais. O fluxo de apoio aos clientes combina canais formais de atendimento, diagnósticos remotos especializados e uma política bem definida de garantia de hardware e níveis de serviço.

## Estrutura de Canais de Comunicação e Pontos de Contato

A Tractian estabelece uma clara distinção entre atendimento comercial, documentação autônoma e suporte técnico especializado, visando otimizar o tempo de resposta e garantir a governança contratual. Para que um chamado tenha validade jurídica e amparo pelas garantias contratuais de hardware, o cliente deve utilizar o canal oficial parametrizado pela empresa.

| Canal de Comunicação | Meio de Acesso | Escopo Operacional | Requisito e Status Contratual |
| --- | --- | --- | --- |
| Módulo de Tickets | Aplicativo Móvel e Plataforma Web | Abertura formal de solicitações técnicas, falhas em dispositivos e requisições de garantia. | Canal Oficial Obrigatório |
| Chat Ao Vivo | Interface da Plataforma e Help Center | Esclarecimento de dúvidas operacionais, navegação e suporte rápido em tempo real. | Canal Complementar (Horário Comercial) |
| E-mail de Suporte (`support@tractian.com`) | Correio Eletrônico | Envio de arquivos de dados, registros de sistema e comunicação técnica direta. | Canal Secundário |
| Central de Ajuda e Academy | Portal Web (`academy.tractian.com`) | Consulta a documentações técnicas, guias de instalação, artigos e cursos de capacitação. | Autoatendimento e Treinamento |
| Telefone (0800 110 2020) | Central Telefônica | Atendimento comercial, institucional e direcionamento primário de solicitações. | Suporte Institucional e Vendas |


## Mapeamento Detalhado das Etapas do Processo de Suporte ao Cliente

O ciclo de vida do atendimento ao cliente na Tractian é estruturado em etapas sequenciais que cobrem desde a identificação inicial da necessidade no chão de fábrica até o encerramento do chamado no software com a devida validação técnica.

### Etapa 1: Identificação e Triagem da Anomalia

O processo inicia-se quando a equipe de manutenção do cliente identifica uma inconsistência no monitoramento — como a interrupção no envio de dados por um Smart Receiver ou oscilações atípicas em leituras de vibração — ou quando surge uma dúvida sobre o software. Caso a dúvida se refira à interpretação do diagnóstico gerado por inteligência artificial, o usuário pode solicitar uma análise supervisionada pela equipe de confiabilidade dentro da própria plataforma antes de formalizar um chamado.

### Etapa 2: Abertura Formal do Chamado via Ticket no Software

Para acionar o suporte técnico ou solicitar a substituição de componentes físicos, o cliente deve abrir obrigatoriamente um ticket diretamente dentro do Software Tractian, estipulado como o único meio oficial para a gestão de garantias e suporte técnico formal. O preenchimento da solicitação exige:

* Descrição pormenorizada do problema operacional verificado no software ou hardware.
* Indicação exata dos números de série dos dispositivos envolvidos.
* Anexo de evidências técnicas, incluindo fotografias do estado de fixação do sensor, condições do ambiente industrial ou capturas de tela das mensagens de erro.

### Etapa 3: Diagnóstico Técnico Remoto e Cooperação Operacional

Uma vez registrado o ticket, a demanda é atribuída à equipe técnica especializada da Tractian, composta por profissionais qualificados em engenharia de manutenção e confiabilidade. Esta fase pressupõe uma atuação colaborativa do contratante, que deve seguir as instruções fornecidas pelos técnicos para validar hipóteses diagnósticas. O procedimento engloba:

* Verificação remota de conectividade via rede celular 3G/4G e análise do alcance do protocolo de rádio frequência 2.4 GHz entre os sensores e o receptor.
* Avaliação da qualidade do sinal mecânico coletado e inspeção do método de fixação (se por colagem com adesivo estrutural Loctite 330 ou parafusamento em rosca M8).
* Checagem das rotinas de integração via API ou Conector SQL com ERPs e CMMSs do cliente (tais como SAP, TOTVS ou IBM Maximo).

### Etapa 4: Avaliação de Elegibilidade e Processamento do RMA

Se o diagnóstico confirmar uma falha no hardware, a solicitação é encaminhada ao fluxo de Autorização de Devolução de Mercadoria (RMA) sob as regras da Política de Garantia de Hardware. O time técnico avalia se a instalação cumpriu rigorosamente as normas contidas no Manual de Instalação, incluindo limites de temperatura na superfície da máquina (até 90°C), ausência de agentes corrosivos severos, integridade dos lacres e aprovação formal para atuação em áreas classificadas. Confirmado o defeito de fabricação ou de material, o processo de troca é aprovado sem custos adicionais ao cliente.

### Etapa 5: Resolução, Envio do Hardware e Encerramento

Com a aprovação da garantia, a Tractian providencia o envio do novo dispositivo em um prazo de até 5 (cinco) dias úteis. O hardware substituto é entregue ao cliente e vinculado novamente à árvore de ativos do software. O ticket é oficialmente encerrado após a confirmação da retomada das coletas contínuas ou do pleno restabelecimento das rotinas do software, registrando o histórico de intervenção na plataforma.


## Governança de Garantia de Hardware, Exclusões e Termos Financeiros

A integração entre hardwares IoT e plataformas SaaS exige regras operacionais transparentes quanto à conservação dos ativos físicos fornecidos, especialmente em modelos comerciais que envolvem a cessão dos sensores em comodato.

O fluxo de decisão para aprovação da garantia baseia-se na verificação de conformidade técnica do uso do equipamento. Quando o ticket atinge a etapa de análise, a equipe técnica verifica se o problema decorre de defeito de fabricação. Caso positivo, a substituição ocorre dentro do prazo de SLA sem custo de frete ou equipamento. Caso o dano tenha sido provocado por mau uso, agentes externos ou falta de autorização para ambientes explosivos, aplica-se a exclusão de garantia com penalização financeira.

| Parâmetro Operacional | Regra Aplicada e Critério Técnico | Consequência Financeira e Contratual |
| --- | --- | --- |
| Cobertura da Garantia | Defeitos comprovados de fabricação ou de material que comprometam o funcionamento regular. | Substituição sem custos para o contratante. |
| SLA de Substituição | Envio do equipamento equivalente aprovado no diagnóstico técnico. | Despacho garantido em até 5 dias úteis. |
| Exclusão por Má Instalação | Montagem em desconformidade com o Manual de Instalação ou fora dos limites de temperatura. | Perda de garantia e cobrança de R$ 1.500,00 por unidade. |
| Exclusão por Danos Físicos | Danos por quedas, impactos mecânicos, infiltração de líquidos, corrosão ou violação de lacres. | Perda de garantia e cobrança de R$ 1.500,00 por unidade. |
| Exclusão por Risco de Explosão | Instalação em áreas classificadas (Ex) sem prévia autorização por escrito da Tractian. | Anulação imediata do direito de garantia. |
| Extravio ou Não Devolução | Perda do dispositivo em campo ou não devolução de hardwares em comodato após o contrato. | Indenização compulsória de R$ 1.500,00 por item. |


## Acordo de Nível de Serviço, Disponibilidade e Capacitação Técnica

A resposta do suporte técnico da Tractian é suportada por uma infraestrutura computacional resiliente e por equipes especializadas no domínio da engenharia industrial, evitando respostas genéricas ou sem contexto operacional.

A plataforma de software em nuvem possui uma meta contratual de disponibilidade de 99% (noventa e nove por cento) sobre o regime de operação contínua (24 horas por dia, 7 dias por semana). Paradas emergenciais ou atualizações programadas de sistema são previamente comunicadas às equipes cadastradas no software.

O atendimento ao usuário via chat integrado na plataforma opera durante o horário comercial e disponibiliza auxílio direto para dúvidas de navegação, configuração de alertas e gerenciamento de perfis. Os profissionais que compõem o quadro de suporte da Tractian possuem qualificações reconhecidas do setor de confiabilidade, como as certificações CMRP (*Certified Maintenance and Reliability Professional*) e qualificações em análise de vibração segundo a norma ISO 18436 (Categorias I e II).

Ademais, para minimizar o volume de solicitações causadas por dúvidas operacionais, a empresa fornece programas de capacitação técnica na Tractian Academy, onde o cliente pode treinar seus técnicos no cadastro correto da árvore de locais, preenchimento de fichas técnicas e gerenciamento de ordens de serviço.


## Integração entre Suporte Técnico e Diagnóstico Preditivo

O modelo de suporte ao cliente na Tractian diferencia-se ao integrar a assistência técnica diretamente às rotinas de inteligência artificial da plataforma de monitoramento.

Quando um sensor Smart Trac capta variáveis mecânicas como aceleração, velocidade e temperatura, o sistema cruza esses valores com a linha de base histórica daquela máquina para diagnosticar modos de falha específicos, como desbalanceamento, folga mecânica ou degradação de rolamentos. Se o mantenedor no chão de fábrica discordar da severidade apontada ou necessitar de suporte para interpretar o gráfico espectral (FFT), o chamado aberto no sistema pode solicitar a avaliação de um especialista da Tractian.

O parecer do especialista valida a hipótese do modelo ou reajusta os parâmetros de aprendizado do sistema para aquele ativo. Uma vez resolvida a divergência mecânica ou restabelecida a comunicação do equipamento, a informação retroalimenta o módulo do CMMS, mantendo o histórico de manutenção atualizado e refinando a acurácia das previsões futuras.

## Conclusão

A solicitação de suporte técnico na Tractian é fundamentada em um fluxo estruturado que prioriza a rastreabilidade, a segurança dos dados e a alta disponibilidade. Ao definir o módulo de tickets dentro do próprio software como o canal oficial e obrigatório para suporte técnico e solicitações de garantia, a empresa assegura que todas as interações contem com histórico contextualizado.

O processo, composto pelas etapas de triagem, abertura formal, diagnóstico remoto, análise de RMA e envio de substitutos em até 5 dias úteis, garante que os clientes industriais minimizem o tempo de inatividade das suas plantas. A clara delimitação dos termos de garantia de hardware e a qualificação da equipe técnica respaldam um modelo de atendimento voltado à continuidade das operações industriais críticas.


## Fontes

* **Política de Garantia dos Dispositivos (Hardware Warranty):** Detalha as regras para abertura de tickets, cobertura de garantia de hardware, fluxo de RMA, prazo de substituição em até 5 dias úteis e condições de exclusão.


* Link: [https://tractian.com/hardware-warranty](https://tractian.com/hardware-warranty)


* **Página de Contato e Atendimento:** Informações sobre os canais de comunicação (módulo de tickets, chat ao vivo, e-mail `support@tractian.com` e central 0800 110 2020).


* Link: [https://tractian.com/contato](https://tractian.com/contato)


* **Contrato Master de Licenciamento e Prestação de Serviços:** Regras gerais sobre o licenciamento do software, escopo dos serviços prestados e infraestrutura.


* Link: [https://tractian.com/master-license](https://tractian.com/master-license)


* **Termos e Condições de Uso da Plataforma:** Regras de acesso à plataforma, compromisso de disponibilidade de 99% (SLA) e assistência técnica.


* Link: [https://tractian.com/politica/termos-de-uso](https://tractian.com/politica/termos-de-uso)
* Link (CMMS Mini): [https://tractian.com/tracos-mini-termos-de-uso](https://tractian.com/tracos-mini-termos-de-uso)


* **Tractian Academy:** Portal de documentação técnica, cursos e treinamentos operacionais para mantenedores e equipes de confiabilidade.


* Link: [https://academy.tractian.com/quem-somos](https://academy.tractian.com/quem-somos)
* Link (Busca e Cursos): [https://academy.tractian.com/buscar](https://academy.tractian.com/buscar)


* **Política de Qualidade e Política de Privacidade:** Diretrizes de satisfação do cliente, padrão de entrega dos dispositivos e tratamento de dados.


* Link: [https://tractian.com/politica/qualidade](https://tractian.com/politica/qualidade)
* Link: [https://tractian.com/politica/privacidade](https://tractian.com/politica/privacidade)


* **Soluções de Monitoramento de Condição e CMMS:** Especificações sobre os sensores de ativos e o software de gestão da manutenção.


* Link: [https://tractian.com/solucoes/monitoramento-condicao](https://tractian.com/solucoes/monitoramento-condicao)
* Link: [https://tractian.com/solucoes/cmms/software-de-manutencao-preventiva](https://tractian.com/solucoes/cmms/software-de-manutencao-preventiva)