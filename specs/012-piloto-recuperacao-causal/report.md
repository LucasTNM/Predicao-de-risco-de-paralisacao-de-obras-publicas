# Resultado — piloto de recuperação causal

**Período:** coleta em29/09/2026; consolidação em30/09/2026. **Escopo:** piloto limitado autorizado, sem coleta massiva ou alteração de rótulos.

## Entrega

Fluxo SpecKit: specify → plan (pesquisa delegada) → tasks → implement → converge. Artefatos em [spec.md](spec.md), [plan.md](plan.md), [tasks.md](tasks.md). Guardas PNCP agora exigem chave oficial explícita e conferência de instituição, instrumento e objeto; removida a extração de sequência do número local e a tentativa indiscriminada em compras/contratos. Sem chave confirmada, o coletor registra pendência e não baixa arquivos. Essa guarda não resolve automaticamente instrumentos antigos sem correspondência oficial.

CLI `scripts/piloto_recuperacao.py` prepara manifesto reproduzível, consulta fontes públicas com cache verificável e consolida resultados. Os dados, respostas, fontes e decisões estão em `logs/piloto_recuperacao/`, ignorado pelo Git. Políticas de rotulagem v1/v2 preservadas.

## Resultado empírico

| Coorte/base | Casos | Identidade confirmada | Causa histórica elegível |
| --- | ---: | ---: | ---: |
| Legado DNIT | 22 | 0 | 0 |
| Novo SISMOB | 24 | 24 | 0 |
| Novo SIMEC | 16 | 0 | 0 |
| Novo CAIXA | 4 | 2 | 0 |
| Novo FUNASA | 5 | 1 | 0 |
| Novo MIDR | 1 | 1 | 0 |
| Novo DNIT | 5 | 0 | 0 |
| Novo SESU / SETEC / SIMEC-Outros | 5 | 0 | 0 |
| Total | 82 | 28 | 0 |

Dos60 novos,39 tiveram consulta específica por identificador (incluindo busca no crosswalk oficial);21 tiveram impedimento antes de uma consulta individual. Acessos ao formulário SIMEC não contam como busca individual bem-sucedida. Foram persistidas90 respostas HTTP únicas, incluindo consultas municipais, detalhes, formulários, crosswalk e históricos. Esses totais não equivalem a90 documentos causais. Reexecução reutilizou82 resultados, verificando hashes das respostas.

Nos22 legados,36 documentos foram examinados e considerados incompatíveis com as obras às quais estavam ligados. A exclusão é lógica nos artefatos do piloto, sem apagar arquivos ou modificar a ponte original. A amostra de catálogo contém25 registros, cinco de cada uma de cinco causas ambíguas; todos continuam pendentes. Detalhes e fundamentação em [revisao.md](revisao.md).

**Rótulos novos:0.** O piloto não encontrou evidência suficiente para reduzir os6.783 casos sem causa. Isso mede o rendimento das rotas testadas, não prova ausência de documentos ou causas em todas as instituições.

## Validação

Testes afetados:97 aprovados em30/09/2026, incluindo identidade, cache/adulteração, corte temporal, CRLF, seleção reproduzível e regressões de rotulagem/coleta. Integração PostgreSQL e auditoria final: pendentes. O engine Docker estava indisponível em30/09; tentativa de inicialização falhou em `sailor-ingest.sock` inacessível. Renomeação do arquivo temporário falhou; remoção foi bloqueada pela revisão automática de aprovação e não executada. Volumes não foram removidos nem redefinidos. T010/T013 permanecem abertos. Não confundir o inventário confirmado em29/09 com nova confirmação do banco em30/09.

## Decisão

Não expandir coleta massiva com estas rotas sem nova fonte causal. Manter NULL; tratar acesso SIMEC, identificadores faltantes e documentos originais como pendências explícitas. A reserva de avaliação é preliminar, por identidade conhecida, sem treino ou gold humano homologado. Riscos e próximos passos em [revisao.md](revisao.md).

## Convergência e retomada
A análise SpecKit identificou ausência de hash do código na retomada e a validação PostgreSQL pendente. T012 implementou hash de implementação por resultado e `coletar --reprocessar`: preserva o resultado anterior, recalcula com respostas íntegras cacheadas e publica a nova proveniência. Resultados foram reprocessados em30/09 sem novas respostas HTTP; respostas continuam datadas da coleta original. A leitura das revisões confere novamente os arquivos originais, respeitando hashes de bytes e normalização CRLF/LF.

T010/T013 dependem do engine Docker operacional. O piloto e a implementação estão entregues, mas a feature não é declarada integralmente validada enquanto a integração e a auditoria ao vivo não forem concluídas. Pendências científicas (novas fontes, adjudicação humana/gold) são distintas desse bloqueio técnico.

## Encerramento da validação — 2026-09-30
Com o Docker operacional, o runner scripts/testar_sprint3.py executou197 testes aprovados em10,77s, incluindo PostgreSQL real em banco descartável. Auditoria somente leitura em isolamento repeatable read confirmou igualdade das60.580 observações completas (fonte, medidas, estados e rótulos) com populacao.json, proveniência válida e0 rótulos em2026. Distribuição2025:0=16.649;1=978;2=104;3=423;NULL=10.134. Evidência em logs/piloto_recuperacao/auditoria_banco_depois.json. T010/T013 concluídas; o bloqueio técnico anterior está resolvido. Pendências científicas de causas e fontes permanecem como resultado do piloto.
