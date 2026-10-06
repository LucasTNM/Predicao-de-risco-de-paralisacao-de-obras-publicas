# Tasks: Avaliação Cega Final no Dataset de Teste Retido (Sprint 6)

## Phase 1: Setup & Foundational
- [x] T001 Implementar testes de integridade pré-avaliação em `tests/test_final_evaluation.py` (auditoria de 3.632 obras, cardinalidade e não-vazamento estrito de `id_tcu`).

## Phase 2: Implementation & CLI (Priority: P1)
- [x] T002 Implementar CLI `scripts/avaliar_teste_retido_sprint6.py` com carregamento, treinamento em lote integral (14.522 obras), inferência no teste cego (3.632 obras) e cálculo de métricas definitivas.

## Phase 3: Verification & Execution (Priority: P1)
- [x] T003 Executar testes automatizados via `pytest tests/test_final_evaluation.py`.
- [x] T004 Executar a avaliação real via `scripts/avaliar_teste_retido_sprint6.py` e gerar relatório `specs/017-avaliacao-teste-retido-sprint6/report.md` e manifesto JSON.

## Phase 4: Polish & Sprint Closure
- [x] T005 Atualizar documentação da Sprint 6 (`docs/Sprints/Sprint6.md`) com as métricas definitivas do teste cego.
- [x] T006 Atualizar `docs/Proximos_Passos.md` e registrar encerramento formal da Sprint 6 via SpecKit.


## Dependencies
T001 -> T002 -> T003 -> T004 -> T005 -> T006.
