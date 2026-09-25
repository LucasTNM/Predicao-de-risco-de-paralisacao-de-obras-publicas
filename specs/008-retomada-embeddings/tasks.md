# Tasks: Pendências documentais e retomada

## Phase 1: Setup
- [x] T001 Criar spec/checklist e desenho em `specs/008-retomada-embeddings/`.

## Phase 2: Foundation
- [x] T002 Restabelecer PostgreSQL local e registrar baseline em `logs/`.

## Phase 3: US1 — evidência documental
- [x] T003 [US1] Reauditar as 27 quarentenas em `logs/sprint3_reauditoria_quarentenas_20260920.json`.
- [x] T004 [US1] Testar e implementar dossiê físico sem promoção de origem em `tests/test_proveniencia.py` e `scripts/auditar_proveniencia_sprint3.py`.
- [x] T005 [US1] Executar dossiê do piloto e registrar disposição em `specs/008-retomada-embeddings/validation.md`.

## Phase 4: US2 — embeddings retomáveis
- [x] T006 [US2] Testar retomada, rollback por lote e corrupção em `tests/test_embedding_run.py` e `tests/test_database_integration.py`.
- [x] T007 [US2] Implementar manifesto congelado (IDs únicos, limite 1..512, batch 1..32), reuso e lote atômico em `src/database/embedding_run.py` e `src/database/embeddings.py`.
- [x] T008 [US2] Implementar CLI limitado em `scripts/gerar_embeddings_sprint4.py`.
- [x] T009 [US2] Executar regressão, lote operacional e retomada e registrar evidências em `specs/008-retomada-embeddings/validation.md`.

## Phase 5: Validação final
- [x] T010 Atualizar Sprint 3/Sprint 4 e executar convergência em `specs/008-retomada-embeddings/validation.md`.

## Dependencies and execution
T001 → T002; US1: T003/T004 → T005; US2: T006 → T007 → T008 → T009; ambas → T010.
Pesquisa de quarentenas pode ocorrer ao lado do desenho técnico; edições compartilhadas
são sequenciais. MVP: dossiê de US1; próximo incremento: execução limitada de US2.
Testes independentes: rejeição de hash para US1; falha no segundo item e retomada
sem encode para US2. Não há tarefa de carga integral ou treinamento nesta feature.

## Phase 6: Convergence

- [x] T011 Rejeitar `--batch-size` fora de 1..32 antes de conectar ao banco, incluindo zero hoje convertido silenciosamente no padrão; adicionar teste de CLI em `tests/test_embedding_run.py`, conforme FR-003/FR-007 e plan: limites explícitos (partial, HIGH).
