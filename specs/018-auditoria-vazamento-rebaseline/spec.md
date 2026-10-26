# Feature Specification: 018-auditoria-vazamento-rebaseline

**Feature Branch**: `018-auditoria-vazamento-rebaseline`

**Created**: 2026-10-19

**Status**: Draft (planejamento — implementação não iniciada)

**Input**: Solicitação do pesquisador: organizar as etapas posteriores à Sprint 6 (Random Forest/LightGBM) antes dos cards de RAG, BERTimbau + LoRA e XAI. Durante o levantamento de contexto, uma auditoria somente leitura (2026-10-19) identificou que fichas sintéticas e a presença/ausência de documentos estão fortemente associadas ao rótulo, exigindo uma etapa de correção antes de qualquer nova modelagem.

## Contexto da evidência (auditoria somente leitura de 2026-10-19)

Obras rotuladas de 2025 (18.154) por composição documental:

| Classe | Total | Sem documentos | Só fichas sintéticas | Só outros documentos |
| :---: | ---: | ---: | ---: | ---: |
| 0 Regular | 16.649 | 9.761 | 6.478 | 410 |
| 1 Técnica | 978 | **966** | 1 | 11 |
| 2 Orçamentária | 104 | 12 | **91** | 1 |
| 3 Abandono | 423 | 0 | **423** | 0 |

Termos no texto das fichas sintéticas, por obra:

| Classe | Obras com ficha | Contém "paralisad" | Contém "em execu" |
| :---: | ---: | ---: | ---: |
| 0 | 6.478 | 2 | 4.859 |
| 1 | 1 | 1 | 0 |
| 2 | 91 | **91** | 0 |
| 3 | 423 | **423** | 0 |

Interpretação: o vetor médio de 768 dimensões usado na Sprint 6 agrega textos que
explicitam a situação "Paralisada" (alvo), e os atributos `has_embedding`,
`num_docs_validos` e `num_chunks_validos` codificam a classe 1 (98,8% sem documentos).
Isso afeta o Artigo I da Constituição ("Fichas sintéticas derivadas de planilhas
DEVEM ser distinguidas de documentos originais para prevenir vazamento do alvo").
As métricas da Sprint 6 são válidas como registro histórico, mas provavelmente
estão **superestimadas**. Esta feature quantifica esse efeito sem apagar o histórico.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Catálogo de vazamento auditável (Priority: P1)

Como pesquisador responsável pela validade científica, quero um relatório
reproduzível que liste cada atributo e cada fonte textual com associação indevida
ao alvo (situação textual em fichas, presença de documentos, base de origem e
imputações calculadas fora do treino), para decidir o que pode entrar nos modelos.

**Why this priority**: Nenhum resultado posterior (LightGBM corrigido, RAG ou
BERTimbau) é defensável perante a banca sem essa auditoria.

**Independent Test**: Executar a auditoria em modo somente leitura e obter as duas
tabelas acima com os mesmos totais, mais a lista de campos das fichas classificados
como "revela alvo", "posterior ao alvo" ou "permitido".

**Acceptance Scenarios**:

1. **Given** o banco de produção em modo somente leitura, **When** a auditoria for executada, **Then** os totais por classe e composição documental coincidem com o contexto acima e nada é gravado no banco.
2. **Given** o modelo textual das fichas sintéticas, **When** os campos forem inventariados, **Then** cada campo recebe uma decisão (remover, mascarar ou manter) com justificativa.

---

### User Story 2 - Rebaseline sem vazamento (Priority: P1)

Como pesquisador, quero reexecutar os modelos de referência da Sprint 6 (Dummy,
Random Forest, LightGBM conjunto e hierárquico campeão) em cenários controlados
para medir quanto do desempenho vinha de vazamento:

- **C0 — Original Sprint 6**: reprodução dos números históricos (controle).
- **C1 — Tabular sem proxies documentais**: sem `has_embedding`, `num_docs_validos` e `num_chunks_validos`.
- **C2 — Texto sem fichas**: embeddings agregados só com documentos não sintéticos.
- **C3 — Fichas mascaradas**: embeddings recalculados com os campos que revelam o alvo removidos.

**Why this priority**: Define o desempenho real de referência que o BERTimbau
precisa superar e corrige a narrativa de resultados do TCC.

**Independent Test**: Validação cruzada agrupada por `id_tcu` (5 dobras, semente 42)
no `treino_dev`, com uma tabela comparativa C0–C3 por modelo.

**Acceptance Scenarios**:

1. **Given** as mesmas partições da Feature 014, **When** os cenários forem executados, **Then** Macro-F1, Balanced Accuracy, MCC, recall por classe e AUC-PR por classe são registrados para cada modelo e cenário.
2. **Given** o cenário eleito como "sem vazamento", **When** ele for avaliado uma única vez no teste retido, **Then** o resultado é registrado como nova referência oficial, preservando a tabela da Sprint 6 como histórico anotado.

---

### User Story 3 - Correção documental das sprints (Priority: P2)

Como autor do TCC, quero que os documentos da Sprint 6 recebam uma nota de revisão
pós-fechamento com o impacto medido, para que a dissertação não afirme
generalização baseada em resultados contaminados.

**Why this priority**: Preserva a honestidade metodológica sem reescrever o histórico.

**Independent Test**: `docs/Sprints/Sprint6.md`, `planos/Sprint6_Plano_de_Implementacao.md` e `specs/017-*/report.md` contêm a nota com link para o relatório desta feature.

**Acceptance Scenarios**:

1. **Given** o relatório da Feature 018, **When** a sprint for encerrada, **Then** as notas de revisão citam números C0 vs. cenário eleito.

### Edge Cases

- Obras que ficam sem texto após remover fichas: tratadas como sem documentos, sem descarte da observação (Art. III).
- Mascaramento que remove todo o conteúdo de uma ficha: a ficha passa a contar como ausente.
- Classe 1 praticamente sem texto: o relatório deve registrar que modelos textuais não podem aprender essa classe com o corpus atual.
- Teste retido já consultado na Sprint 6: a nova avaliação é única, pré-registrada e documentada como reutilização controlada.
- Imputação por mediana calculada no próprio conjunto avaliado (`extract_tabular_features`): deve passar a usar estatísticas do treino.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A auditoria DEVE operar somente em leitura sobre o banco de produção.
- **FR-002**: O sistema DEVE produzir inventário dos campos textuais das fichas sintéticas com decisão por campo (remover/mascarar/manter) e justificativa.
- **FR-003**: O sistema DEVE gerar embeddings agregados por obra para os cenários C2 e C3 sem alterar `tcc.dim_embedding` (artefatos derivados em `dados_processados/sprint7/`).
- **FR-004**: Os vetores de chunks mascarados (C3) DEVEM ser gerados com o mesmo modelo/revisão GTE da Sprint 4 e registrados em manifesto com hash.
- **FR-005**: Imputação, codificação e pesos DEVEM ser ajustados apenas na partição de treino de cada dobra.
- **FR-006**: O sistema DEVE reportar Macro-F1, Balanced Accuracy, MCC, recall/precisão por classe, AUC-PR por classe e matriz de confusão para cada modelo × cenário.
- **FR-007**: O cenário oficial sem vazamento DEVE ser escolhido apenas pela validação cruzada, antes de consultar o teste retido.
- **FR-008**: O sistema DEVE preservar as partições, os rótulos e os artefatos da Sprint 6 sem regravação.
- **FR-009**: O relatório DEVE declarar a lista final de atributos e fontes textuais permitidas para as Features 019–021.

### Key Entities

- **Catálogo de Vazamento**: atributo/fonte, tipo de associação com o alvo, evidência quantitativa e decisão.
- **Cenário Experimental**: identificador (C0–C3), atributos incluídos, fontes textuais incluídas e hash dos artefatos.
- **Referência Oficial Corrigida**: modelo + cenário eleitos e métricas no teste retido.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos campos das fichas sintéticas classificados com decisão justificada.
- **SC-002**: Reprodução do cenário C0 com diferença de Macro-F1 ≤ 0,005 em relação à Sprint 6.
- **SC-003**: Tabela comparativa com os 4 cenários × 4 modelos concluída e documentada.
- **SC-004**: Zero fragmentos que mencionem a situação da obra nos insumos do cenário eleito (verificação por busca de termos).
- **SC-005**: Uma única avaliação do cenário eleito no teste retido, registrada antes da redação dos resultados.

## Assumptions

- Os rótulos (Sprint 5) e partições (Feature 014) permanecem válidos; o problema está nos atributos, não no alvo.
- A GPU local (RTX 5060) e o ambiente `.venv-sprint4-gpu` comportam recalcular vetores dos ~14,7 mil chunks de fichas de 2025.
- O cenário C2 deve ter desempenho muito inferior para as classes 2 e 3; isso é um resultado científico, não uma falha.
- A decisão final sobre o uso de fichas mascaradas na modelagem textual será validada com o orientador.
