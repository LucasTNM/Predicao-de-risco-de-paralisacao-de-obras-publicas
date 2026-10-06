# Tasks: Inicialização autônoma Docker
## Phase 1: Setup
- [x] T001 Formalizar artefatos e pesquisa em specs/013-inicializacao-docker/; checklist16/16 aprovado e hooks ausentes.
## Phase 2: Foundation
- [x] T002 Criar testes de preparo, timeout e conexão em tests/test_docker_runtime.py e tests/test_database_connection.py.
## Phase 3: US1 — Retomada
Teste independente: engine fechado solicita início uma vez e aguarda saúde; aberto reutiliza.
- [x] T003 [US1] Implementar supervisor com orçamento e contexto local em src/docker_runtime.py.
- [x] T004 [US1] Integrar scripts/preparar_docker.py, scripts/testar_sprint3.py e src/database/connection.py.
- [x] T005 [US1] Testar ciclo real com Desktop parado e comparar dados em logs/docker_runtime/ciclo_frio.json.
## Phase 4: US2 — Diagnóstico
Teste independente: falha por estágio, remoto/auth sem intervenção, tempo limitado.
- [x] T006 [US2] Validar diagnósticos e isolamento, registrar limites em specs/013-inicializacao-docker/report.md.
## Phase 5: Polish
- [x] T007 Executar regressões PostgreSQL e auditoria; registrar em specs/013-inicializacao-docker/report.md.
- [x] T008 Atualizar AGENTS.md e documentos da sprint; encerrar features012/013 com speckit-converge.
## Dependencies
T001→T002→T003→T004→T005; T006 apósT003; T007–T008 após validação. Testes de módulos podem executar juntos; lifecycle real apenas sem cargas concorrentes.
## Implementation strategy
Supervisor isolado primeiro, integração depois, ciclo real e preservação antes de declarar startup comprovado. Sem treino/coleta/mudança de rótulo.

## Phase 6: Convergence
- [x] T009 Restringir endpoints npipe ao pipe local e unix a caminho absoluto local em src/docker_runtime.py; testar pipe remoto em tests/test_docker_runtime.py, conforme FR-004/US2 e Constituição IV (partial, HIGH). A inspeção de contexto aceitava todo prefixo npipe, inclusive host remoto.
