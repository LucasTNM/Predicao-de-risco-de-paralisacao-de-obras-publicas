# Tasks: Preparação do Dataset, Particionamento e Quarentena Documental

## Phase 1: Setup
- [x] T001 Criar estrutura do pacote `src/dataset/` (`src/dataset/__init__.py`) e diretório de destino `dados_processados/sprint6/`.

## Phase 2: Foundational
- [x] T002 [P] Implementar catálogo e filtro de quarentena documental em `src/dataset/quarantine.py`, carregando os 36 documentos DNIT da Feature 012.
- [x] T003 [P] Criar testes unitários e de integração em `tests/test_dataset_preparation.py` para quarentena, não-vazamento de grupos e integridade dimensional.

## Phase 3: User Story 1 - Extração tabular e agregação vetorial com quarentena (Priority: P1)
- [x] T004 [US1] Implementar extração dimensional 1:1 e pooling de embeddings por obra em `src/dataset/extractor.py`.
- [x] T005 [US1] Integrar quarentena dos 36 documentos e flag `has_embedding` no extrator em `src/dataset/extractor.py`.

## Phase 4: User Story 2 - Particionamento estratificado por identidade de obra sem vazamento (Priority: P1)
- [x] T006 [US2] Implementar partição estratificada 80/20 por grupos de `id_tcu` com semente determinística (42) em `src/dataset/partition.py`.
- [x] T007 [US2] Implementar conferência estrita de interseção de grupos (`set(dev) & set(test) == empty`) e balanço de classes em `src/dataset/partition.py`.

## Phase 5: User Story 3 - Isolamento de 2026, reserva de pendentes e manifesto (Priority: P2)
- [x] T008 [US3] Implementar segregação de 2026 e isolamento dos casos pendentes de 2025 em `src/dataset/partition.py`.
- [x] T009 [US3] Implementar CLI `scripts/preparar_dataset_sprint6.py` com exportação de datasets em Parquet e manifesto JSON com hashes SHA-256.

## Phase 6: Polish
- [x] T010 Executar testes automatizados em `tests/test_dataset_preparation.py` e regressão geral em `scripts/testar_sprint3.py`.
- [x] T011 Executar a geração real dos datasets via `scripts/preparar_dataset_sprint6.py` e registrar evidências em `specs/014-dataset-particoes-quarentena/report.md`.
- [x] T012 Atualizar documentos de sprint (`docs/Proximos_Passos.md`, `planos/Sprint5_Plano_de_Implementacao.md`) e validar convergência via `speckit-converge`.


## Dependencies
T001 -> T002/T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010 -> T011 -> T012.

## Parallel opportunities
- T002 e T003 podem ser desenvolvidos em paralelo após T001.
- Testes unitários de particionamento e de quarentena são independentes.

## Implementation strategy
1. Setup e guardas de quarentena primeiro.
2. Extrator e agregação vetorial com banco real em seguida.
3. Particionamento estrito por `id_tcu` e validação matemática de não-vazamento.
4. Exportação Parquet e manifesto SHA-256.
5. Validação integral com PostgreSQL real e fechamento com speckit-converge.
