# Tasks: Carga Documental 2025 e Auditoria 2026

## Phase 1: Setup & Baseline
- [x] T001 Registrar estado baseline do banco de dados antes da carga em logs/carga_2025_banco_antes.json
- [x] T002 Iniciar auditoria física isolada de 2026 em background via src/database/run_load.py

## Phase 2: US1 — Execução da Carga de 2025 (P1)
- [x] T003 [US1] Executar a carga oficial dos documentos de 2025 via src/main.py com exclusão de quarentenas
- [x] T004 [US1] Monitorar progresso e registrar checkpoints em logs/

## Phase 3: US2 — Validação Pós-Carga (P1)
- [x] T005 [US2] Executar validação relacional e de integridade do banco via src/database/validation.py
- [x] T006 [US2] Executar testes de regressão automatizados em scripts/testar_sprint3.py

## Phase 4: Polish & Converge
- [x] T007 Consolidar evidências e métricas finais em specs/005-carga-documental-2025/validation.md
