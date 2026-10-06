# Sprint 5 — situação, causa e recuperação (v2)
**Data:** 2026-09-28. **Feature:** 011-situacao-causa-risco. **Estado:** regra v2 aplicada; recuperação documental preparada; causas sem prova permanecem pendentes.

## Decisão do pesquisador
Situação é a entrada principal. Em execução/Concluída sem causa contraditória => classe 0. Paralisada => consultar causa e atribuir 1 técnica, 2 financeira ou 3 abandono; causa ausente exige recuperação documental da própria obra.

Confirmação explícita: “Sim, usar 0 pela situação sem contradições”. Constituição atualizada pelo SpecKit para 2.0.0 porque redefine a regra de classe 0 anterior. Zero é referência tabular de regularidade; não é prova por auditoria de que não existe risco. Corte de 2025 preservado.

## Resultado aplicado no banco
| Classe / estado de 2025 | Quantidade |
| --- | ---: |
| 0 — regular pela situação | 16.649 |
| 1 — deficiência técnica | 978 |
| 2 — deficiência orçamentário-financeira | 104 |
| 3 — abandono | 423 |
| NULL — pendente | 10.134 |
| Total | 28.288 |

18.154 fatos rotulados. Os zeros se dividem em 11.050 Em execução e 5.599 Concluída. Permanecem 88 Em execução e 82 Concluída com contradição (causa ou origem), além de 9.964 Paralisadas ainda pendentes. Todas as 32.292 observações de 2026 permanecem NULL.

A aplicação v2 gravou somente os 16.649 zeros, reutilizou 1.505 rótulos antigos e preservou conteúdo não relacionado à rotulagem. Conferência independente comparou as 1.505 proveniências originais v1 com o banco: igualdade integral, inclusive datas e hashes.

## Paralisadas sem causa: tratamento implementado
6.783 obras de 2025 têm causa ausente/não informada: 6.738 SQL NULL e 45 hífen/Não informado.

| Encaminhamento do pacote | Obras |
| --- | ---: |
| Coletar original: nenhum documento vinculado | 498 |
| Coletar original: somente ficha sintética | 6.263 |
| Confirmar vínculo, origem, data e causa nos documentos | 22 |

Os 22 casos têm 36 documentos vinculados; 13 obras possuem trechos localizados por termos de paralisação/risco. Isso não significa 13 causas comprovadas: amostra inclui cláusulas condicionais genéricas e documentos possivelmente de outros objetos, como evento técnico e serviço de monitoramento. A verificação de pertencimento ao contrato é obrigatória.

O comando recuperar exporta identidade/snapshot, documentos, caminhos/hashes, até três trechos candidatos com offsets por obra e próxima ação. Exclui fichas sintéticas dos trechos probatórios e não usa textos de outra obra. Não inventa causa a partir de percentual financeiro, classe modal ou similaridade vetorial. Nenhuma das 6.783 recebeu classe por essa recuperação; o pacote é a etapa operacional de obtenção/verificação de evidência.

Com fonte original adequada, importar revisão de classe 1–3 usando o guia da feature 010: revisor, justificativa, arquivo UTF-8, hash, data até a data-base e trecho literal. Sem evidência, manter NULL e excluir do treino causal supervisionado.

## Implementação e testes
- policy_v2.py adiciona R00 e auditoria multiversão; policy.py v1 permanece congelada.
- Método regra_situacao distingue zeros de causas por regra e decisões humanas.
- Recuperação por obra via CLI recuperar, sem escrita no banco.
- Reuso de versões antigas sem regravar proveniência; decisões divergentes continuam bloqueadas.
- 178 testes aprovados em 9,22 s, incluindo PostgreSQL descartável, situações/origens conflitantes, causalidade ausente, isolamento por obra e preservação v1/v2.
- Primeira tentativa de aplicação falhou na conexão durante indisponibilidade temporária do PostgreSQL, antes de gravar. Docker voltou saudável; repetição concluiu com sucesso. Nenhum volume reiniciado/apagado pelo agente.

## Artefatos
[Plano](plan.md), [protocolo vigente](protocolo-rotulagem.md), [guia](quickstart.md) e [tarefas](tasks.md). Relatórios locais: logs/sprint5_v2_simulacao.json, sprint5_v2_aplicacao.json, sprint5_v2_retomada.json, sprint5_v2_recuperacao.json, sprint5_v2_preservacao_v1.json, sprint5_v2_auditoria.json, sprint5_v2_integridade.json e sprint5_v2_regressao.txt.

## Continuidade
Próximo trabalho é obter evidências originais para os 6.761 casos sem fonte utilizável e revisar os 22 com documentos não confirmados; em paralelo, revisar 3.181 paralisadas com causa ambígua/multicausal e 170 conflitos em situações regulares. Não há novo treinamento. A rotulagem operacional não encerra homologação científica nem comprova previsão futura.


## Auditoria final
Reexecução: 18.154 reusos, zero updates. Auditoria de proveniência e validate_data válidos, dez contadores de inconsistência zerados. Fingerprints confirmam preservação entre primeira carga v1, v2, retomada e auditoria final; vetores incluídos na comparação. Nenhum commit/push realizado nesta execução.

SpecKit converge: sem lacunas técnicas; 9/9 tarefas de implementação concluídas. Recuperação de causas permanece dependente de fontes adequadas, conforme limitações acima.

## Avaliação das pendências — 2026-09-29

A avaliação com SpecKit separou as 9.964 paralisadas pendentes em 3.181 com causa presente não resolvida e 6.783 sem causa utilizável. Após ativação do Docker, consulta somente leitura confirmou os totais, a distribuição documental por base e a validade dos rótulos existentes; nenhum registro de 2026 está rotulado. Nenhum rótulo ou código foi alterado nesta avaliação.

Recomenda-se revisar o catálogo das causas presentes e, para causas ausentes, conferir a identidade dos vínculos PNCP antes de um piloto de recuperação histórica: 22 obras DNIT com documentos não confirmados mais 60 casos novos distribuídos entre as bases, com maior participação de SISMOB/SIMEC. Ausência de evidência mantém `label_risco = NULL`; cancelamento, ficha sintética e similaridade textual não comprovam causa.

A feature 011 permanece entregue no escopo técnico original. O piloto, correções dos coletores e revisão científica são trabalho futuro proposto, ainda não executado, a detalhar em nova spec/plan/tasks antes da implementação. Consulte a [avaliação e critérios de decisão](avaliacao-pendencias-20260929.md), o [roadmap de recuperação](roadmap-recuperacao.md) e a [análise de consistência SpecKit](analise-speckit-20260929.md).

## Execução do piloto causal — 2026-09-30

O roadmap foi executado como feature012 pelo SpecKit. Manifesto com22 legados e60 novos, amostra reproduzível por base/situação original, respostas públicas cacheadas e revisões declaradas pelo assistente.36 documentos dos22 legados DNIT foram considerados incompatíveis com as obras e colocados em quarentena lógica no piloto; arquivos/ponte do banco preservados. A guarda PNCP agora exige identificador oficial e valida instituição/instrumento/objeto, sem reutilizar número local como sequência.

Nos60 novos:28 identidades confirmadas (24 SISMOB,2 CAIXA,1 FUNASA,1 MIDR), nenhuma causa histórica elegível.16 casos SIMEC tiveram barreira reCAPTCHA;11 casos não têm identificador compatível com as rotas implementadas;5 instrumentos adicionais não constam no crosswalk.39 casos tiveram consulta específica por identificador (incluindo seis tentativas alternativas SIMEC no crosswalk), não60 buscas individuais bem-sucedidas.25 causas tabulares ambíguas foram revistas e permanecem pendentes. Nenhum novo rótulo atribuído.

Não expandir a mesma rota SISMOB em massa sem fonte causal complementar. Priorizar acesso legítimo ao SIMEC, mapeamentos de identidade e documentação histórica. Reserva preliminar por identidade:5.669 observações para avaliação,22.619 para desenvolvimento; não é gold homologado nem dataset de treino aprovado.

Validação local:97 testes passaram. Integração e auditoria final PostgreSQL pendentes por falha de inicialização do Docker (`sailor-ingest.sock`); tarefasT010/T013 abertas. Não houve reset de volumes. [Relatório completo](../012-piloto-recuperacao-causal/report.md), [revisão científica e limites](../012-piloto-recuperacao-causal/revisao.md) e [tarefas](../012-piloto-recuperacao-causal/tasks.md).
