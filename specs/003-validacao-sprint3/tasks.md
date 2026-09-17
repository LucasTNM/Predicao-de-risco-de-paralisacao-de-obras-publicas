# Tasks: Validação e correções da Sprint 3

**Input**: spec.md, plan.md, research.md, data-model.md e contracts/cli.md.

## Phase 1: Setup

- [x] T001 Instalar Spec Kit em .venv e gerar .specify/ e .agents/skills/ via agy.
- [x] T002 Formalizar nove ADRs em .specify/memory/constitution.md.

## Phase 2: Foundational

- [x] T003 Especificar a revisão em specs/003-validacao-sprint3/spec.md e plan.md.
- [x] T004 Registrar baseline e decisões em specs/003-validacao-sprint3/research.md.

## Phase 3: US1 — Governança (P1)

Teste independente: CLI, YAML das skills e regras de versionamento.

- [x] T005 [US1] Fixar specify-cli em requirements.txt e documentar exceções locais em .gitignore.
- [x] T006 [US1] Validar .agents/skills/*/SKILL.md e os scripts da feature em .specify/scripts/powershell/.

## Phase 4: US2 — Integridade (P1)

Teste independente: corpus sintético e PostgreSQL descartável, sem mutar o banco de carga.

- [x] T007 [US2] Reproduzir falhas físicas/qualidade em tests/test_database_preflight.py antes das correções.
- [x] T008 [US2] Reproduzir retomada com vínculos/conteúdo alterados em tests/test_database_integration.py.
- [x] T009 [US2] Corrigir validação prévia e revalidação em src/database/preflight.py e load_documentos.py.
- [x] T010 [US2] Conferir ocorrências completas e conteúdo antes do reuso em src/database/load_documentos.py.
- [x] T011 [US2] Testar/corrigir portabilidade da assinatura e integridade em src/database/schema.py e validation.py.
- [x] T012 [US2] Testar/corrigir gravação atômica e falha de relatório em src/database/run_load.py e tests/test_database_reporting.py.

## Phase 5: US3 — Evidências (P2)

Teste independente: suite completa e relatório confrontável com saída real.

- [x] T013 [US3] Tornar tests/test_higienizacao.py independente de chave Gemini e scripts/testar_sprint3.py compatível com Pytest.
- [x] T014 [US3] Executar Pytest e integração real; registrar resultados em specs/003-validacao-sprint3/validation.md.
- [x] T015 [US3] Conferir corpus/banco acessíveis em leitura e corrigir alcance das conclusões em docs/Sprints/Sprint3.md e validation.md.

## Phase 6: Polish

- [x] T016 Revisar diffs, executar quickstart e speckit-converge para specs/003-validacao-sprint3/tasks.md.

## Dependencies & Execution Order

T001–T004 → US1 → testes US2 → correções US2 → US3 → converge.
Testes devem falhar pelo defeito antes da correção e passar depois.

## Parallel Opportunities

US1: YAML e regras Git podem ser inspecionados independentemente.
US2: pesquisa de schema/validação paralela à análise de preflight/loader.
US3: inspeção somente leitura do corpus independe da base de teste.
Mutações no mesmo arquivo ou banco de teste seguem sequência única.

## Implementation Strategy

Governança é o primeiro incremento verificável. Cada correção posterior inclui
reprodução e teste. Concluir com relatório e convergência, sem commit automático.

## Phase 7: Preflight físico — refinamento de performance

- [x] T017 [US2] Limitar a cinco leituras concorrentes e dez documentos pendentes em src/database/preflight.py, preservando ordem e quarentenas; validar equivalência em tests/test_database_preflight.py.
- [x] T018 [US3] Expor progresso do preflight físico em src/database/run_load.py e registrar a execução real em validation.md.

## Phase 8: Fechamento solicitado

- [x] T019 Revisar regras de exclusão e arquivos rastreados conforme FR-010.
- [x] T020 Produzir e revisar visualmente relatório local das Sprints 2 e 3 conforme FR-011.
- [x] T021 Testar conteúdo selecionado, conferir escopo e preparar publicação do commit da Sprint 3 na branch de trabalho conforme FR-012; limite da integração atual em validation.md.
