# Validação — Sprint 5 / feature 010

Data: 2026-09-28. Checklist de requisitos: 10/10 PASS. Hooks: .specify/extensions.yml ausente, nenhum hook registrado. Artefatos criados via fluxo specify → setup-plan → setup-tasks → check-prerequisites → implement.

## Matriz de rastreabilidade

| Requisito | Evidência | Resultado |
| --- | --- | --- |
| FR-001 taxonomia | PCC PDF 17/28, research, protocolo, policy.py e testes exatos | PASS |
| FR-002 corte/pendência | testes temporais/conflito e auditoria de 32.292 observações 2026 NULL | PASS |
| FR-003 inventário | logs/sprint5_inventario_final.json: 60.580 fatos; fila de 28.288 em 2025 | PASS |
| FR-004 revisão 0–3 | 4 classes testadas, fonte/hash/data/trecho/revisor e casos inválidos | PASS técnico; nenhuma revisão humana real importada |
| FR-005 persistência | lote real 1.505, reexecução zero updates, comparação exata das 1.505 proveniências; rollback/locks em banco isolado | PASS |
| FR-006 invalidação/auditoria | testes causa, medida, situação, origem e pacto; carga idêntica preservada; validate_data válido | PASS |
| FR-007 preservação/testes | 158 testes em 8,22 s; hashes de cinco tabelas iguais antes/após/retomada/auditoria | PASS |
| FR-008 documentação | plano local, Sprint5, diário, próximos passos, backlog e artefatos versionáveis | PASS |

SC-001: inventário integral. SC-002: todas as proveniências válidas, sem classe 0 automática/2026. SC-003: retomada real sem atualizações; rollback real em teste. SC-004: contagens e fingerprints preservados. SC-005: guia de revisão utilizável e lacuna científica explícita.

US1: três cenários cobertos (regras, desconhecidos, 2026). US2: três cenários cobertos por testes (zero, conflitos justificados, snapshot/fonte alterados). US3: três cenários cobertos (reuso/divergência, falha, relatório com método). Revisão humana do corpus não foi executada pelo agente.

## Integridade real
60.580 obras e fatos, 51.009 documentos, 185.789 chunks/vetores, 232.902 vínculos. validate_data: válido; dez contadores de inconsistência zerados. Nenhum vetor recomputado; preservação exata por hash integral incluindo os valores vetoriais.

## Constituição e decisões técnicas
Quatro princípios verificados: temporalidade/rótulo, integridade textual, esquema dimensional e reprodutibilidade. Cinco decisões de arquitetura verificadas: catálogo exato, proveniência no esquema existente, revisão validada, transação/invalidação, ausência de treino. .gitattributes fixa LF no módulo cuja assinatura constitui a versão da política. Dados e logs permanecem ignorados pelo Git.

## Limite de aceite
Aceite técnico não é homologação científica. 26.783 pendentes em 2025; classe 0 real ainda ausente. Autenticidade da evidência e identidade do revisor são declarações humanas, não validações criptográficas de autoria. O campo histórico rotulo_preenchido_sem_homologacao em validate_data agora conta proveniências inválidas; seu zero não declara homologação científica.


## Convergência Spec Kit final
Converged: implementação satisfaz spec, plan e tarefas do escopo técnico. Conferidos 8 FR + 5 SC + 9 cenários de aceite, 6 decisões de pesquisa e 4 princípios constitucionais. Zero findings missing/partial/contradicts/unrequested; zero tarefas anexadas. O comando converge preservou tasks.md; a etapa de implementação posterior apenas marcou T016 concluída após registrar o resultado. 16/16 tarefas técnicas concluídas. Sem hooks configurados.

Pendências científicas foram deliberadamente excluídas do aceite automático e continuam abertas no relatório: evidências regulares, ambiguidades e homologação. A sprint de rotulagem permanece parcial quanto à cobertura do corpus.
