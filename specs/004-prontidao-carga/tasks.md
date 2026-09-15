# Tasks: Prontidão antes da carga

## Phase 1: Setup
- [x] T001 Formalizar requisitos e desenho em specs/004-prontidao-carga/ antes da implementação.

## Phase 2: Foundational
- [x] T002 Registrar baseline do banco em logs/ e verificar proteção de fontes/segredos em .gitignore.

## Phase 3: US1 — Auditoria integral (P1)
Teste independente: falha/interrupção mantém relatório; dry-run não conecta ao banco.
- [x] T003 [US1] Reproduzir lacunas de relatório em tests/test_database_reporting.py.
- [x] T004 [US1] Publicar checkpoints, inventários e fingerprints em src/database/run_load.py.
- [x] T005 [US1] Executar auditoria integral dos dois anos e preservar resultados em logs/.

## Phase 4: US2 — Destinação (P1)
Teste independente: cada ocorrência tem decisão, evidência e condição de reentrada.
- [x] T006 [US2] Investigar ocorrências e gerar destinação individual em logs/.
- [x] T007 [US2] Registrar escopo elegível e pendências científicas em specs/004-prontidao-carga/validation.md.

## Phase 5: US3 — Preparação reproduzível (P2)
Teste independente: roteiro coerente, regressão aprovada e banco preservado.
- [x] T008 [P] [US3] Corrigir sequência em docs/Sprints/Sprint3.md e guia versionável specs/004-prontidao-carga/quickstart.md; alinhar help/saída e validação somente leitura em src/main.py.
- [x] T009 [US3] Executar regressão/integração isolada com scripts/testar_sprint3.py e registrar evidências em validation.md.
- [x] T010 [US3] Conferir banco em leitura, revisar proteção de arquivos e consolidar estado versionável do projeto.

## Phase 6: Polish
- [x] T011 Executar speckit-converge e registrar cobertura em specs/004-prontidao-carga/validation.md.

## Dependencies & Execution Order
T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T009/T010 -> T011.
T008 independe da leitura física do corpus e pode ocorrer durante T005.
US1 é o MVP; US2 depende de seus resultados. Relatórios parciais nunca concluem T005.

## Implementation Strategy
Testes primeiro, alterações pequenas, execução real completa, destinação conservadora,
revisão e evidência. Não carregar banco operacional nem alterar fontes.

## Phase 7: Refinamento de revisão
- [x] T012 [US2] Fazer parecer bloqueado impedir conexão de escrita sem exclusão explícita em src/database/run_load.py e src/main.py; testar elegível + quarentena e elegível + exclusão em tests/test_database_reporting.py (FR-003).
