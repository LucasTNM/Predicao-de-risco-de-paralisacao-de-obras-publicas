# Tasks: Auditoria de Vazamento e Rebaseline (Sprint 7)

**Status**: Concluído e auditado em 2026-10-19 — 12/12 tarefas finalizadas com sucesso.

## Phase 1: Setup
- [x] T001 Versionar os scripts de auditoria somente leitura (base: consultas de 2026-10-19) em `scripts/auditar_vazamento_sprint7.py`.
- [x] T002 Criar perfis de atributos por cenário (C0–C3) em `src/modeling/loader.py` e passar a imputar medianas com estatísticas do treino.

## Phase 2: User Story 1 — Catálogo de vazamento (P1)
- [x] T003 [US1] Inventariar os campos do modelo de ficha sintética e gravar `catalogo_vazamento.md` com decisão por campo.
- [x] T004 [US1] Implementar `src/dataset/masking.py` e testes em `tests/test_masking.py` (nenhum termo de situação remanescente; offsets registrados).
- [x] T005 [US1] Implementar `src/dataset/leakage_audit.py` e `tests/test_leakage_audit.py`.

## Phase 3: User Story 2 — Rebaseline (P1)
- [x] T006 [US2] Gerar agregados C2 (sem fichas) e C3 (fichas mascaradas, vetores GTE recalculados) em `dados_processados/sprint7/` com manifesto SHA-256.
- [x] T007 [US2] Executar `scripts/rebaseline_sprint7.py` (4 modelos × 4 cenários × 5 dobras; Macro-F1, BA, MCC, AUC-PR).
- [x] T008 [US2] Pré-registrar no `report.md` o cenário eleito pela validação cruzada.
- [x] T009 [US2] Avaliar o cenário eleito uma única vez no teste retido.

## Phase 4: User Story 3 — Documentação (P2)
- [x] T010 [US3] Redigir `report.md` com a tabela C0–C3 e a lista final de fontes permitidas para 019–021.
- [x] T011 [US3] Adicionar nota de revisão em `docs/Sprints/Sprint6.md`, `planos/Sprint6_Plano_de_Implementacao.md` e `specs/017-*/report.md`.
- [x] T012 Rodar `pytest` completo e o runner `scripts/testar_sprint3.py` antes do commit.

## Dependencies
T001 → T002 → (T003 → T004, T005) → T006 → T007 → T008 → T009 → T010 → T011 → T012.
