# Tasks: Modelagem Supervisionada com Priorização do LightGBM e Baselines

## Phase 1: Setup
- [x] T001 Criar estrutura do pacote `src/modeling/` (`src/modeling/__init__.py`).

## Phase 2: Foundational
- [x] T002 Implementar carregador de dados Parquet e montador de matrizes tabulares/vetoriais em `src/modeling/loader.py`.
- [x] T003 Implementar motor de métricas científicas multiclasse em NumPy puro em `src/modeling/metrics.py`.
- [x] T004 Implementar particionador de validação cruzada agrupado por `id_tcu` (5 dobras) em `src/modeling/splitter.py`.

## Phase 3: User Story 1 - Baselines de Referência (Priority: P1)
- [x] T005 [US1] Implementar classificadores baseline (`DummyClassifier` e Random Forest tabular) em `src/modeling/baselines.py`.

## Phase 4: User Story 2 & 3 - Motor LightGBM e Ponderação de Classes (Priority: P1)
- [x] T006 [US2, US3] Implementar motor de treinamento LightGBM para alta dimensionalidade (768d) com GOSS, histogramas e pesos de classe balanceados em `src/modeling/lightgbm_engine.py`.
- [x] T007 [US2, US3] Implementar orquestrador comparativo de validação cruzada (tempo, memória e métricas) em `src/modeling/evaluator.py`.

## Phase 5: Verification & CLI (Priority: P2)
- [x] T008 [P] Criar testes unitários em `tests/test_modeling.py` cobrindo carregamento, métricas, divisão sem vazamento e treinamento LightGBM.
- [x] T009 [P] Implementar CLI oficial `scripts/treinar_sprint6.py` com geração de manifesto de métricas e relatório Markdown.

## Phase 6: Polish & Execution
- [x] T010 Executar os testes automatizados com pytest em `tests/test_modeling.py`.
- [x] T011 Executar o benchmarking real completo via `scripts/treinar_sprint6.py` e registrar evidências em `specs/015-modelagem-lightgbm-baseline/report.md`.
- [x] T012 Verificar convergência com SpecKit e atualizar histórico da Sprint 6.


## Dependencies
T001 -> T002/T003/T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010 -> T011 -> T012.
