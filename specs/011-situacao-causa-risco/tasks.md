# Tasks — extensão da Sprint 5
## Phase 1: Governance and setup
- [X] T001 Registrar autorização de zero pela situação em .specify/memory/constitution.md e specs/011-situacao-causa-risco/.
## Phase 2: US1 — regra situação
- [X] T002 [US1] Escrever testes de situação/causa/origem/corte em tests/test_labeling_v2.py antes do código.
- [X] T003 [US1] Implementar R00 e despacho histórico em src/labeling/policy_v2.py; manter policy.py imutável.
## Phase 3: US2 — recuperação
- [X] T004 [US2] Testar fichas sintéticas, documento de outra obra, ausência e trechos limitados em tests/test_labeling_v2.py.
- [X] T005 [US2] Implementar pacotes por obra em src/labeling/recovery.py e recuperar em scripts/rotular_sprint5.py.
## Phase 4: US3 — operação e preservação
- [X] T006 [US3] Integrar reuso multiversão/método em src/database/labeling.py e testar v1/v2 em tests/test_labeling_integration.py.
- [X] T007 [US3] Executar regressão PostgreSQL, simulação/aplicação/reexecução/recuperação/auditoria e salvar logs/sprint5_v2_*.
## Phase 5: Documentation and convergence
- [X] T008 Atualizar docs/Sprints/Sprint5.md, diário, próximos passos, plano e protocolo; registrar resultados em specs/011-situacao-causa-risco/report.md.
- [X] T009 Conferir implementação via SpecKit converge e registrar specs/011-situacao-causa-risco/validation.md.

Dependências: T001 -> T002/T004 -> T003/T005 -> T006 -> T007 -> T008/T009. Testes puros das duas histórias independentes; integração após ambas. MVP regra R00, seguido de recuperação; nenhuma marcação de revisão humana concluída sem evidência. Teste independente US1: tabela de situações; US2: encaminhamentos próprios; US3: banco real/reuso v1/v2.
