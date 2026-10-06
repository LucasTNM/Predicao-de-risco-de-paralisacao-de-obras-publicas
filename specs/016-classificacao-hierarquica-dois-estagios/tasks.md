# Tasks: Classificação Hierárquica em Dois Estágios para Risco e Causas de Paralisação

## Phase 1: Setup & Foundational
- [x] T001 Implementar detector binário de risco (Estágio 1: `BinaryRiskDetector`) em `src/modeling/hierarchical.py`.
- [x] T002 Implementar classificador multiclasse condicional (Estágio 2: `ConditionalCausalClassifier`) em `src/modeling/hierarchical.py`.
- [x] T003 Implementar orquestrador hierárquico `TwoStageHierarchicalClassifier` (soft cascade, hard cascade e limiares operacionais) em `src/modeling/hierarchical.py`.

## Phase 2: Verification & Testes
- [x] T004 [P] Criar suíte de testes unitários em `tests/test_hierarchical_modeling.py` cobrindo binarização, condicionamento causal, predição probabilística $(N, 4)$ e coerência dos limiares.
- [x] T005 [P] Executar testes automatizados com `pytest tests/test_hierarchical_modeling.py`.

## Phase 3: Execution & Benchmarking (Priority: P1)
- [x] T006 Implementar CLI `scripts/treinar_hierarquico_sprint6.py` para avaliação em 5 dobras agrupadas por `id_tcu` e comparação direta com a Feature 015.
- [x] T007 Executar o treinamento experimental completo via `scripts/treinar_hierarquico_sprint6.py` e gerar manifesto JSON.
- [x] T008 Consolidar resultados e evidências em `specs/016-classificacao-hierarquica-dois-estagios/report.md`.

## Phase 4: Polish & Documentation
- [x] T009 Atualizar documentação da Sprint 6 (`docs/Sprints/Sprint6.md`) e próximos passos (`docs/Proximos_Passos.md`).
- [x] T010 Validar conformidade constitucional e registrar encerramento da feature via SpecKit.


## Dependencies
T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010.
