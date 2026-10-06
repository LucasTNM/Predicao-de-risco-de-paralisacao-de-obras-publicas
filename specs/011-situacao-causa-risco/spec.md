# Feature Specification: Sprint 5 — situação, causa e recuperação
**Branch**: codex/sprint5-rotulagem | **Created**: 2026-09-28 | **Status**: validada pelo esclarecimento do pesquisador.

## User Scenarios & Testing
### US1 — Situação primeiro (P1)
Pesquisador quer situação Em execução/Concluída => 0 se não houver contradição. Paralisada => causa orienta 1–3.
Teste independente: casos de situação, causa e origem. Aceites: regular sem causa vira zero; regular com causa/origem contraditória fica pendente; paralisada nunca vira zero por falta de causa; 2026 permanece fora do corte.
### US2 — Recuperar causa ausente (P1)
Pesquisador quer ação concreta para paralisadas sem causa. Gerar pacote por obra com documentos vinculados, trechos candidatos e próxima ação de verificação/coleta.
Teste independente: fichas sintéticas não servem como prova; trechos de outra obra não entram; obra sem documento recebe ação de coleta. Aceites: toda paralisada sem causa tem encaminhamento; trecho recuperado nunca vira rótulo apenas por similaridade/palavra-chave.
### US3 — Preservar histórico e aplicar (P1)
Pesquisador quer novos zeros sem invalidar os 1.505 rótulos anteriores. Aceites: auditoria suporta v1/v2 e reexecução não altera origem; divergência bloqueia escrita.

## Requirements
- FR-001: Classificar pela situação primeiro. Em execução/Concluída, causa ausente (NULL, vazio, hífen ou Não informado), origem sem contradição => 0 com regra R00 e proveniência tabular.
- FR-002: Contradições incluem causa presente e origem paralisada/cancelada/inacabada/rescindida/reiniciada/não executada/com pendência. Marcador SEM PENDÊNCIA não é COM PENDÊNCIA. Outras situações não geram zero.
- FR-003: Paralisada com causa usa catálogo v1; sem causa aciona recuperação documental da própria observação de 2025; 2026 não pode preencher causa histórica.
- FR-004: Exportar pacote integral de recuperação com identidade, snapshot, documentos, origem, caminhos/hash e até três trechos candidatos por obra, com id_documento/id_embedding/posição/offset. Origem não confirmada exige revisão; sintéticas são excluídas dos trechos probatórios; sem material => nova coleta original.
- FR-005: Não inventar causa; sem prova a label permanece NULL com encaminhamento. Revisão existente importa 1–3 com prova original, data e justificativa.
- FR-006: Auditar políticas versionadas sem alterar módulo v1 nem reescrever proveniências válidas antigas; manter simulação, transações e fingerprints.
- FR-007: Atualizar constituição mediante decisão explícita, protocolo, sprint, diário e próximos passos; testes unitários/integração e operação real.

## Success Criteria
- SC-001: Todos os zeros aplicados satisfazem situação/causa/origem e corte; nenhuma paralisada sem causa recebe zero.
- SC-002: 100% das paralisadas sem causa de 2025 entram no pacote de recuperação, inclusive sem documentos.
- SC-003: 1.505 decisões v1 preservadas integralmente; segunda aplicação zero updates e auditoria válida.
- SC-004: Testes reais aprovados e conteúdo alheio à rotulagem preservado.

## Assumptions
Autorização explícita: “Sim, usar 0 pela situação sem contradições”. Zero é referência operacional tabular, não laudo de inexistência de risco. Origem reiniciada pede revisão de cronologia. Rótulos positivos não mudam nesta extensão. Recuperação automatiza preparação de evidência; fonte inadequada exige nova coleta, não imputação da classe modal. Não executar coleta externa indiscriminada nem treinamento nesta entrega. Manter corte 2025 conforme decisão anterior; imagem de 2026 ilustra colunas, não altera alvo temporal.
