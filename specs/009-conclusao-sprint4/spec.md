# Feature Specification: Conclusão técnica da Sprint 4

**Created**: 2026-09-23
**Status**: Concluída tecnicamente e validada
**Input**: Reauditar embeddings, planejar e executar até alimentar integralmente Dim_Embedding e disponibilizar busca vetorial no PostgreSQL, com relatório final.

## User Scenarios & Testing
### US1 — Auditoria reproduzível (Priority: P1)
Como pesquisador, quero verificar os vetores existentes antes de ampliar o processamento.
**Why**: Evitar propagar corrupção ou mistura de modelos.
**Independent Test**: Revisão ausente ou vetor divergente deve reprovar a auditoria.
**Acceptance**: Conferir 100% dos vetores existentes e recomputar os 157 do baseline; registrar diferenças numéricas, modelo, revisão e integridade.

### US2 — Corpus integral pesquisável (Priority: P1)
Como operador, quero gerar representações de todos os chunks já aceitos no banco, com retomada após falhas.
**Why**: Entregar o objetivo operacional da sprint.
**Independent Test**: Uma execução interrompida retoma sem alterar conteúdos nem repetir vetores concluídos.
**Acceptance**: Todos os chunks da seleção inicial têm vetor válido; cada lote confirma atomicamente; a retomada completa reutiliza todos.

### US3 — Busca e encerramento auditável (Priority: P1)
Como usuário, quero consultar documentos por similaridade com filtros e conhecer o alcance da entrega.
**Why**: Tornar os vetores utilizáveis e a conclusão verificável.
**Independent Test**: Consultar texto de um chunk e recuperar seu próprio conteúdo com distância próxima de zero; ano/origem não vazam.
**Acceptance**: Busca por texto retorna ranking e proveniência; medir latência; relatório distingue conclusão técnica de qualidade científica.

### Edge Cases
Revisão nula, modelo divergente, fonte alterada, falta de memória ou disco, reinício, lote parcial, seleção adulterada, corpus alterado durante execução, filtros vazios e vetores já preenchidos.

## Requirements
- **FR-001** Reauditar integridade e proveniência de todos os vetores iniciais, com recomputação e tolerância documentada.
- **FR-002** Congelar todo o corpus elegível já carregado, com revisões fixadas; não truncar texto ou incorporar quarentenas.
- **FR-003** Processar integralmente em lotes atômicos, com retomada idempotente e relato de falhas, sem sobrescrever incompatíveis.
- **FR-004** Preservar documentos, conteúdo, tokens, vínculos, fatos, rótulos e distinção entre anos/origens.
- **FR-005** Disponibilizar busca por texto com ranking por similaridade, filtros aplicados antes do top-k e proveniência.
- **FR-006** Medir tempo, recursos, latência e qualidade técnica; escolher busca exata ou índice conforme evidência.
- **FR-007** Registrar dependências, configuração, testes, auditoria final, decisão e limitações nos documentos da Sprint 4.

### Key Entities
Corpus congelado; subexecução retomável; vetor com proveniência; consulta com filtros; relatório de auditoria.

## Success Criteria
- **SC-001** 100% dos vetores iniciais auditados; nenhum erro inexplicado de reprodução.
- **SC-002** 100% dos chunks congelados com vetores válidos e compatíveis; zero pendentes.
- **SC-003** Zero inconsistências relacionais, nenhuma alteração de conteúdo/rótulos e retomada sem novos vetores.
- **SC-004** Consultas de autocorrespondência recuperam o conteúdo; consultas temáticas e filtros têm resultados verificáveis e latência registrada.
- **SC-005** Testes aprovados e relatório final publicado localmente nos documentos da sprint.

## Assumptions and scope decision
O usuário autorizou explicitamente a carga integral em 2026-09-23. Esta decisão substitui o limite operacional das features 007/008 para a nova feature, preservando os comandos limitados existentes. A qualidade semântica assistida já medida será reportada com suas limitações; a carga técnica não homologa relevância humana, rótulos, treino, Random Forest ou uso histórico de 2026. Nenhuma aprovação humana será inventada. Busca exata satisfaz o objetivo; HNSW só será incluído se a medição justificar sua complexidade.
