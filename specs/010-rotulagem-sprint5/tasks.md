# Tasks: Sprint 5 — rotulagem histórica
Input: spec.md, plan.md, research.md, data-model.md e contracts/cli.md. Testes exigidos por FR-007.

## Phase 1: Setup
- [X] T001 Formalizar fonte PCC, catálogo conservador e plano completo em specs/010-rotulagem-sprint5/research.md e planos/Sprint5_Plano_de_Implementacao.md.
- [X] T002 Verificar ambientes, Docker, .gitignore e .dockerignore; preservar credenciais/corpus locais.

## Phase 2: Foundational
- [X] T003 Definir snapshot canônico e módulo src/labeling/__init__.py conforme data-model.md; label_risco inteiro exato em {0,1,2,3} ou NULL, booleanos proibidos.

## Phase 3: US1 — regras e inventário
Teste independente: todas as classes causais e pendências produzem decisões estáveis sem escrever.
- [X] T004 [US1] Escrever testes de regras, negativas, causas múltiplas e corte temporal em tests/test_labeling.py e observar falha inicial.
- [X] T005 [US1] Implementar catálogo, hash e classificação exata em src/labeling/policy.py; 2026 e ausência de causa permanecem NULL.
- [X] T006 [US1] Implementar leitura, inventário e simulação em src/database/labeling.py e scripts/rotular_sprint5.py.

## Phase 4: US2 — revisão e persistência
Teste independente: decisões 0–3 com prova válida; rejeição integral de decisão inválida.
- [X] T007 [US2] Testar revisão, zero, hash/trecho/datas e duplicação em tests/test_labeling.py antes de implementar.
- [X] T008 [US2] Implementar validação em src/labeling/policy.py e importação em scripts/rotular_sprint5.py; revisor/justificativa não vazios, evidencia.origem=original e data até data_base.
- [X] T009 [US2] Implementar lote transacional, bloqueio concorrente, origem JSON, idempotência e recusa de divergências em src/database/labeling.py.

## Phase 5: US3 — integridade e operação
Teste independente: rollback/reexecução/contexto alterado detectados; preservação do corpus.
- [X] T010 [US3] Escrever testes PostgreSQL de rollback, concorrência, revisão, reuso e invalidação em tests/test_labeling_integration.py antes de integrar loader/auditor.
- [X] T011 [US3] Invalidar rótulos na alteração de fonte em src/database/load_obras.py e validar proveniência em src/database/validation.py.
- [X] T012 [US3] Implementar fingerprints e distribuição auditável em src/database/labeling.py; corpus/medidas preservados.
- [X] T013 [US3] Executar regressão real via scripts/testar_sprint3.py e registrar logs/sprint5_regressao.txt.
- [X] T014 [US3] Executar inventário, simulação, aplicação, retomada e auditoria reais; registrar evidências em logs/sprint5_*.json.

## Phase 6: Documentation and convergence
- [X] T015 Atualizar docs/Sprints/Sprint5.md, docs/TCC_Dev_Diary.md, docs/Proximos_Passos.md, planos/README.md e specs/010-rotulagem-sprint5/report.md.
- [X] T016 Executar SpecKit converge e registrar verificação final em specs/010-rotulagem-sprint5/validation.md, sem fingir homologação humana.

## Dependencies & Execution Order
T001–T003 antes de US1; US2 usa snapshot de US1; US3 integra ambas. T013 antes de T014; documentação após evidências. Catálogo e revisão compartilhando policy.py são sequenciais. Pesquisa/leitura e testes independentes podem ser paralelizados, sem edições concorrentes do mesmo arquivo.

## Implementation Strategy
MVP: inventário/regras/simulação; depois revisão e persistência; finalmente carga real e auditoria. A sprint técnica pode encerrar com pendências de rotulagem explícitas. Revisão científica externa não é tarefa marcada concluída pelo agente. Treinamento não integra estas tarefas.
