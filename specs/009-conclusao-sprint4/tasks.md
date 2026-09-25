# Tasks: Conclusão técnica da Sprint 4
## Phase 1: Setup
- [x] T001 Especificar objetivo integral e decisão de escopo em `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli.md`, `quickstart.md`.
- [x] T002 Verificar ambiente/recursos e preparar dependências reprodutíveis em `requirements-sprint4-gpu.txt` e `logs/`.
## Phase 2: Foundation
- [x] T003 Testar/corrigir revisão nula e filtro de origem em `tests/test_database_integration.py`, `tests/test_embedding_run.py`, `src/database/validation.py`, `scripts/gerar_embeddings_sprint4.py`.
## Phase 3: US1 — auditoria
- [x] T004 [US1] Implementar auditoria integral e fingerprints em `scripts/auditar_embeddings_sprint4.py`.
- [x] T005 [US1] Recomputar vetores iniciais e validar CPU/GPU em `logs/`, registrar resultado em `validation.md`.
## Phase 4: US2 — carga integral
- [x] T006 [US2] Testar congelamento, adulteração e retomada em `tests/test_sprint4_corpus.py` e `tests/test_database_integration.py`.
- [x] T007 [US2] Implementar orquestrador/CLI em `src/database/embedding_corpus.py` e `scripts/concluir_embeddings_sprint4.py`, registrar dispositivo em `src/database/embedding_run.py`.
- [x] T008 [US2] Validar modelo/dispositivo/precisão e batch em `src/embedding_model.py` e `logs/`.
- [x] T009 [US2] Executar carga integral retomável e registrar progresso em `logs/` e `validation.md`.
- [x] T010 [US2] Auditar todos os vetores finais, comparar fingerprints e repetir retomada em `logs/`.
## Phase 5: US3 — busca
- [x] T011 [US3] Disponibilizar consulta textual em `scripts/buscar_embeddings_sprint4.py` com filtros e proveniência.
- [x] T012 [US3] Executar autocorrespondência, filtros, consultas temáticas e latência em `scripts/validar_busca_integral_sprint4.py`; registrar decisão de índice em `validation.md`.
## Phase 6: Encerramento
- [x] T013 Executar regressão oficial em `scripts/testar_sprint3.py` e convergência Spec Kit.
- [x] T014 Publicar `report.md` e atualizar `specs/007-piloto-embeddings/`, `specs/008-retomada-embeddings/` e documentos locais de Sprint4 com resultados e limitações.

## Dependencies
T001→T002/T003→T004/T005→T006/T007/T008→T009→T010→T012→T013→T014.
T011 pode ser preparado enquanto a carga roda. US1 é MVP auditável; US2 completa cobertura; US3 entrega uso e relatório. Testes antes de escrita operacional. Toda tarefa inclui arquivo e critério definido nos artefatos.
## Parallel opportunities
Pesquisa readonly e preparação CUDA podem ocorrer durante desenho; implementação compartilhada sequencial. Durante US2, preparar consultas/relatório sem alterar o corpus. Dentro de US1, verificações de ambiente são independentes do desenho dos testes.

## Phase 7: Convergence

- [x] T015 [US3] Completar autocorrespondência consultando pelo texto do próprio chunk, além do vetor persistido, em `scripts/validar_busca_integral_sprint4.py`; executar no banco integral e atualizar evidências/relatório conforme US3/Independent Test e SC-004 (partial, HIGH).
