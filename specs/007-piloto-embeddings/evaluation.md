# Avaliação de custo e recuperação — 2026-09-19

Atualização técnica de 2026-09-20: a [feature 008](../008-retomada-embeddings/validation.md)
implementou lotes retomáveis e adicionou 32 vetores de 2025, totalizando 157.
A retomada reutilizou todos os 32; 84 testes aprovados e integridade validada.
A auditoria física cobre 160 documentos. As métricas abaixo continuam referidas
ao universo de 125 conteúdos de 2026-09-19; não foram extrapoladas aos novos vetores.

## Decisão

Manter o piloto de 125 vetores e a busca exata. Custo e espaço foram medidos,
mas a avaliação assistida encontrou recuperação insuficiente para consultas de
causa de risco. Não iniciar carga integral, HNSW ou treinamento com esta evidência.
Uma busca aproximada não resolve a falta de pertinência observada na busca exata.

## Custo: T012 concluída

Auditoria: **185.789/185.789** chunks, mesma assinatura de identidades da auditoria
de 16/09 (`5eae4d17528f2894d83574e1831709a8d81c06f02c037c5f70c1c4970b4b5625`).
Zero excedentes. Tokenização integral: 26,73 s. Amostra: 59 conteúdos em nove faixas,
selecionados por hash, três repetições (177 inferências medidas), batch 2 em CPU,
8 threads; aquecimento separado. Nenhuma escrita no banco: 125 vetores antes/depois.

| Tokens GTE (limite superior) | População | Amostra | Mediana por lote da faixa |
|---|---:|---:|---:|
| 128 | 5.061 | 8 | 0,630 s |
| 256 | 34.396 | 8 | 1,418 s |
| 384 | 31.151 | 8 | 2,230 s |
| 512 | 114.954 | 8 | 2,710 s |
| 640 | 99 | 8 | 3,354 s |
| 1.024 | 40 | 8 | 5,146 s |
| 2.048 | 85 | 8 | 10,611 s |
| 4.096 | 2 | 2 | 4,914 s |
| 8.192 | 1 | 1 | 5,586 s |

Projeção: somatório de `população_faixa × segundos_por_chunk_faixa` = **54.309 s
(15,09 h)**. Min/max das repetições: 14,99–15,43 h; **não é intervalo de confiança**.
Pico de working set: **2.675.322.880 bytes**. Pressupõe agrupamento por comprimento;
exclui leitura, escrita, WAL, índice, auditorias e inicialização. A seleção cobre a
distribuição de comprimento, sem ser prova de qualidade semântica ou SLA de produção.

Relatório: `logs/sprint4_benchmark_20260919_192356_357173.json`.

## Espaço

- PGDATA `/var/lib/postgresql/data`, volume `tcc-sprint3_postgres_data`, container
  `tcc-sprint3-postgres-1`, porta publicada `127.0.0.1:5432`.
- Filesystem do volume: **1.022.463.787.008 bytes livres** (capacidade virtual Linux).
- VHDX encontrado em `C:/Users/lucas/AppData/Local/Docker/wsl/disk/docker_data.vhdx`;
  host: **114.323.791.872 bytes livres**, conforme snapshot separado.
- Payload vetorial integral: **572.230.120 bytes**. Reserva inicial de planejamento:
  **2.288.920.480 bytes (4x)**, disponível nos dois níveis. O fator 4 é uma hipótese
  explícita, não medida de WAL/TOAST nem orçamento para HNSW; conferir novamente antes
  de qualquer carga longa.

Snapshot do host: `logs/sprint4_espaco_host_20260919.json`.

## Revisão assistida de relevância

Os dois pacotes originais foram lidos: 73 conteúdos no recorte 2025 e 63 em 2026,
125 únicos. Revisor: **Codex, assistente IA**, sem atribuir revisão ao usuário ou
professor. Julgamentos binários completos e justificativas ficam nos pacotes locais
`sprint4_revisao_20260919_155902_010329_assistida_ia.json` e
`sprint4_revisao_20260919_155947_188881_assistida_ia.json`, em `logs/`.

Limitações: rubrica formulada durante inspeção, sem pré-registro, um único revisor
IA e sem cegamento completo (rankings de 2025 já haviam aparecido na sessão anterior).
Não é gold standard. A homologação humana de T011 permanece pendente.

Critérios: menção explícita ao tema, sem deduzir causa a partir de percentual,
saldo zero ou estado administrativo. Cláusulas condicionais pertinentes podem ser
relevantes para busca, mas não provam ocorrência de risco. Escolas/creches exigem
identificação do empreendimento; texto padronizado sobre infraestrutura educacional
não transforma hospital universitário em escola. Casos ambíguos foram excluídos
conservadoramente e devem ser adjudicados por revisor humano.

### Precisão@5 no universo misto

| Consulta | 2025 | 2026 |
|---|---:|---:|
| Recursos/pagamentos | 0,00 | 0,00 |
| Falhas técnicas | 0,00* | 0,20 |
| Descumprimento da contratada | 0,00* | 0,20 |
| Condições de obras rodoviárias | 0,00* | 0,00 |
| Unidades de saúde | 0,80 | 0,80 |
| Escolas/creches | 0,60 | 1,00 |

\* Não há relevante julgado no pequeno universo 2025 para essas três consultas;
recall é **indefinido**, não zero nem sucesso. Não extrapolar ausência ao corpus inteiro.
Saúde: recall@5 0,286 (2025) e 0,571 (2026). Educação: 0,429 e 1,000.
Relatórios com todas as métricas por consulta:
`logs/sprint4_busca_20260919_192754_608878.json` e
`logs/sprint4_busca_20260919_192820_611844.json`.

### Comparação por origem

O filtro `original` retornou vazio em ambos os anos. O piloto contém:

| Ano | Ficha sintética: chunks | Origem não confirmada: chunks |
|---|---:|---:|
| 2025 | 48 | 25 |
| 2026 | 24 | 39 |

Não foi alterada a origem. Comparação exploratória com `nao_confirmada`, preservando
julgamentos idênticos dos conteúdos compartilhados e validando suas chaves/textos:

| Consulta | P@5 2025 misto → não confirmada | P@5 2026 misto → não confirmada |
|---|---:|---:|
| Recursos/pagamentos | 0,00 → 0,20 | 0,00 → 0,40 |
| Falhas técnicas | 0,00* → 0,00* | 0,20 → 0,40 |
| Descumprimento da contratada | 0,00* → 0,00* | 0,20 → 0,20 |
| Condições rodoviárias | 0,00* → 0,00* | 0,00 → 0,00 |

Para saúde/educação esse filtro remove todos os relevantes do piloto, logo não é
um substituto universal para a busca mista. São universos diferentes e a comparação
não é experimento controlado de desempenho do modelo. O resultado sugere separar
busca temática de busca de evidência causal e melhorar proveniência/amostragem;
não justifica escolher um limiar de similaridade ou trocar o modelo sem novo ensaio.

Relatórios: `logs/sprint4_busca_20260919_192953_188569.json` e
`logs/sprint4_busca_20260919_193017_910401.json`. A revisão foi reutilizada em
subconjuntos, sem acrescentar julgamento de novos textos.

## Verificação

**74 testes aprovados**, incluindo PostgreSQL descartável, cálculo ponderado,
amostragem limitada/determinística, faixas, parser de espaço e autoria explícita
da revisão. O benchmark e as avaliações operacionais são somente leitura.
T012 concluída; T009/T011 parciais. Próxima evidência necessária: adjudicação humana
e amostra com documentos de origem confirmada, incluindo relevantes de risco.

## Decisão posterior — 2026-09-23
O usuário autorizou explicitamente a conclusão técnica integral. A [feature009](../009-conclusao-sprint4/spec.md) assume esse escopo, preservando os julgamentos assistidos e pendências de adjudicação humana desta avaliação. Gerar os vetores e disponibilizar busca não homologa relevância científica. A execução operacional ainda depende da recuperação do Docker/PostgreSQL; nenhuma nova contagem foi confirmada nesta data.

### Execução da decisão posterior
Carga integral concluída e verificada em 2026-09-23: 185.789 vetores válidos, 55 min 46 s, retomada integral sem novas gravações. Mediana SQL de 177,5 ms justificou manter busca exata. Os números e julgamentos do piloto acima continuam referidos ao seu universo original; não foram extrapolados à população completa. Ver [relatório final](../009-conclusao-sprint4/report.md).
