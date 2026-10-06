# Validação — feature 011

Data: 2026-09-28. Checklist Specify: 6/6 PASS. Fluxo: constitution → specify → setup-plan → setup-tasks → check-prerequisites → implement. Hooks não configurados.

| Requisito | Evidência | Estado |
| --- | --- | --- |
| FR-001 situação primeiro | 16.649 zeros, regra R00, método regra_situacao; testes da matriz | PASS |
| FR-002 contradições | testes origem/cause, SEM vs COM PENDÊNCIA; 170 regulares pendentes | PASS |
| FR-003 causa/corte | regras causais v1 preservadas; 2026 não alterado | PASS |
| FR-004 pacote | 6.783 obras com encaminhamento, docs e até 3 trechos próprios | PASS |
| FR-005 não inventar | zero rótulos por recuperar; revisão documental continua disponível | PASS |
| FR-006 versões | 1.505 origens v1 idênticas; 18.154 reusos/zero updates na retomada | PASS |
| FR-007 docs/testes | constituição 2.0.0, docs atualizados, 178 testes/9,22 s | PASS |

SC-001 audit_labels válido e testes; SC-002 pacote integral 6.783, inclusive sem docs; SC-003 comparação de origens/fingerprints e reexecução real; SC-004 178 testes reais e validate_data válido.

Integridade: 60.580 obras/fatos, 51.009 documentos, 185.789 vetores, 232.902 vínculos. Dez contadores de inconsistência zerados. Fingerprints de cinco tabelas iguais entre aplicação v1, antes/depois v2, retomada e auditoria final, excluindo apenas campos autorizados do rótulo. Os vetores integram o hash de preservação.

Limitações explícitas: recuperação não é adjudicação. 6.761 obras precisam de fonte original (498 sem docs + 6.263 só sintéticas); 22 exigem conferência documental. 13 têm trechos candidatos, sem causalidade comprovada. Autoria/autenticidade de futuras revisões continuam responsabilidade do pesquisador. Corte 2025 inalterado. Zero por situação é referência tabular autorizada e não prova científica de inexistência de risco.


## SpecKit converge
Converged: 7 requisitos, 4 critérios de sucesso, 8 aceites das três histórias e 4 princípios constitucionais verificados contra código/testes/evidências. Zero lacunas missing/partial/contradicts/unrequested no escopo técnico. Nenhuma tarefa anexada; tasks.md preservado durante converge. Depois, implementação marcou T009 pela conferência concluída. 9/9 tarefas técnicas concluídas. Pendências de obtenção/adjudicação de evidência permanecem explícitas e não foram marcadas concluídas.
