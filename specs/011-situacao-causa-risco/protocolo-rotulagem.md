# Protocolo vigente — situação e causa (v2)

**Autorização:** pesquisador em 2026-09-28: “Sim, usar 0 pela situação sem contradições”. Constituição 2.0.0. Substitui a exigência v1 de revisão documental para toda classe 0; não altera as quatro categorias do PCC nem o corte até 2025.

| Situação | Causa | Decisão |
| --- | --- | --- |
| Em execução / Concluída | Ausente/não informada e sem contradição na origem | Classe 0; método regra_situacao |
| Em execução / Concluída | Presente, ou origem contraditória | Revisar conflito |
| Paralisada | Informada e mapeada | Classe 1/2/3 conforme causa |
| Paralisada | NULL/vazia/hífen/Não informado | Recuperar causa na própria obra; não atribuir zero |
| Paralisada | Genérica/multicausal/ambígua | Revisar contexto antes de escolher 1/2/3 |
| Outra situação ou 2026 | Qualquer | Não atribuir por esta política |

As situações originais com paralisação, cancelamento, rescisão, inacabamento, reinício, não execução/início, ausência de etapa útil ou COM PENDÊNCIA bloqueiam zero. SEM PENDÊNCIA não é contradição. A classe 0 indica referência tabular de situação regular, sem alegação de auditoria documental ou probabilidade nula de risco.

## Recuperação de causa

1. Identificar obra/data-base, instrumento e documentos efetivamente vinculados.
2. Verificar se o documento pertence ao contrato e ao corte histórico. Um vínculo no banco, por si só, não prova isso.
3. Procurar laudo de vistoria, relatório de auditoria, termo de paralisação/rescisão ou justificativa factual que declare o motivo. Trechos localizados por palavras-chave servem para leitura, não para inferir automaticamente classe.
4. Excluir fichas sintéticas derivadas da planilha como fonte de causa nova. Se só existem essas fichas ou não há documentos, coletar original no órgão gestor/portal oficial.
5. Registrar fonte, SHA-256, data, trecho literal, responsável e justificativa. Importar a revisão causal pela CLI existente.
6. Sem evidência suficiente, manter a causa original intacta e label_risco NULL, acompanhada da próxima ação no pacote de recuperação. Não imputar causa por maioria, percentual físico/financeiro ou semelhança com outra obra.

## Limite do material atual
Levantamento: 6.783 paralisadas de 2025 com causa ausente/não informada (6.738 SQL NULL mais 45 equivalentes). 6.263 só com fichas sintéticas, 498 sem documentos e 22 com origem não confirmada. Nas 22, há 36 documentos vinculados e 13 obras com trechos candidatos. Esses 13 não são 13 causas comprovadas: amostra inclui cláusulas genéricas e documentos possivelmente de outro objeto. Verificar vínculo, cronologia e fato antes de rotular.

## Histórico
policy.py v1 permanece congelado; policy_v2.py usa regra R00 e mantém catálogo causal v1. Proveniências já válidas são auditadas pela versão original e não reescritas por atualização cosmética. Decisão divergente exige resolução explícita.
