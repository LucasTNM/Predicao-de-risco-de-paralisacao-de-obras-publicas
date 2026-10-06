# Tasks: Piloto de recuperação causal
## Phase 1: Setup
- [x] T001 Formalizar spec/plan/research/data-model/contracts/quickstart em specs/012-piloto-recuperacao-causal/ e verificar ignores.
## Phase 2: Foundational
- [x] T002 Escrever testes de identidade, seleção, persistência e corte em tests/test_pncp_identity.py e tests/test_recovery_pilot.py.
## Phase 3: US1 — Identidade
Teste independente: sequência local bloqueada; chave oficial validada; arquivo não relacionado não aceita vínculo.
- [x] T003 [US1] Implementar guardas PNCP em src/extractors/pncp_identity.py e integrar src/main.py e src/extractors/pncp.py.
- [x] T004 [US1] Auditar documentos dos22 legados e exportar quarentena em src/labeling/pilot.py e logs/piloto_recuperacao/auditoria_legados.json.
## Phase 4: US2 — Piloto
Teste independente:22+60 distintos e seleção estável; HTTP/login/CAPTCHA distinguíveis; retomada com hash.
- [x] T005 [US2] Implementar manifesto estratificado e CLI preparar em src/labeling/pilot.py e scripts/piloto_recuperacao.py.
- [x] T006 [US2] Implementar consultas oficiais e cache auditável em src/labeling/pilot_sources.py.
- [x] T007 [US2] Processar60 casos novos e conferir82 resultados/impedimentos (busca ou impedimento por caso) em logs/piloto_recuperacao/.
## Phase 5: US3 — Revisão e escala
Teste independente: sem evidência não há label; métricas por fonte/coorte e reserva por identidade.
- [x] T008 [US3] Revisar amostra de catálogo e todos os candidatos recuperados em specs/012-piloto-recuperacao-causal/revisao.md e logs/piloto_recuperacao/.
- [x] T009 [US3] Gerar decisão de escala e dataset/reserva em src/labeling/pilot.py e logs/piloto_recuperacao/.
## Phase 6: Polish
- [x] T010 Executar testes afetados e auditoria PostgreSQL; registrar resultados em specs/012-piloto-recuperacao-causal/report.md.
- [x] T011 Atualizar docs/Sprints/Sprint5.md, docs/TCC_Dev_Diary.md, docs/Proximos_Passos.md e planos/Sprint5_Plano_de_Implementacao.md; executar speckit-converge.
## Dependencies
T001→T002→T003→T004; T005 usa seleção e população; T006 depende dos contratos pesquisados; T007 dependeT003–T006; T008–T009 dependemT007; T010–T011 encerram.
## Parallel opportunities
Leituras das fontes e código são independentes; testes dos módulos podem rodar juntos. Escritas no mesmo manifesto sempre sequenciais. Pesquisa delegada somente conforme speckit-plan.
## Implementation strategy
Entregar guardas primeiro; em seguida manifesto/coleta limitada; depois revisão/resultados. Bloqueio externo permanece explícito e não vira recuperação fictícia.

## Phase 7: Convergence
- [x] T012 Registrar hash da implementação e impedir reuso silencioso de resultado gerado por código diferente; permitir reprocessamento explícito das respostas cacheadas em scripts/piloto_recuperacao.py e testar em tests/test_recovery_pilot.py, conforme FR-005/SC-004 e Constituição IV (partial, HIGH).
- [x] T013 Concluir a evidência de integração e auditoria PostgreSQL de T010, registrando resultados em specs/012-piloto-recuperacao-causal/report.md quando o Docker estiver operacional, conforme FR-009/SC-004 (partial, HIGH; dependência externa).
