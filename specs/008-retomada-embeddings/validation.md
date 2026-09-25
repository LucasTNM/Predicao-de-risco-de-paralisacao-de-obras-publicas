# Validação — 2026-09-20

## Sprint 3: pendências e cadeia documental

Reauditoria de 27 quarentenas em `logs/sprint3_reauditoria_quarentenas_20260920.json`:
27 PDFs com hash físico conforme e 27 textos com tamanho conforme.

| Disposição | Quantidade | Condição para resolução |
|---|---:|---|
| Coleta ausente sem alternativa confirmada | 22 | Recuperar registro verificável de coleta |
| Duplicata física de três PDFs aceitos da mesma obra | 1 | Reconciliação explícita de alias, sem inventar coleta |
| SIMEC com duas obras por arquivo | 3 | Homologar os vínculos documentais |
| Qualidade residual (score 0,983330; limite 0,30) | 1 | Rehigienizar e produzir novo manifesto |

Nenhuma reentrada automática: a carga de 2026 permanece parcial. A duplicata agora
tem evidência física; sua destinação não equivale à criação de uma coleta aceita.

O dossiê `logs/sprint3_proveniencia_20260920_154555_602806.json` conferiu os 134
documentos ligados aos 125 vetores iniciais. Após o novo lote,
`logs/sprint3_proveniencia_20260920_154727_393724.json` conferiu **160/160** documentos:
hashes de PDF/texto, coleta aceita e estados de extração/higienização OK.
Origem permanece como registrada; integridade física não homologa originalidade.

## Sprint 4: execução e retomada

Nova CLI: `scripts/gerar_embeddings_sprint4.py`. Seleção congelada com checksum no JSON,
até 512 conteúdos; lotes atômicos de até 32, padrão 8; inferência interna de 2.
GTE/modelo/código externo fixados conforme feature 007, CPU e normalização L2.
São registrados hashes dos módulos, versões das bibliotecas e tentativas.
O banco determina itens concluídos na retomada; conteúdo/tokens/configuração são
revalidados. Vetores existentes incompatíveis bloqueiam execução.

Executado `--limite 32 --ano 2025 --origem nao_confirmada --write`:
32 novos vetores, em quatro lotes. Evidência da primeira execução preservada em
`logs/sprint4_lotes_20260920_154650_211744_primeira_execucao.json`.
Retomada do mesmo manifesto: **32 reutilizados**, nenhuma nova inferência;
`logs/sprint4_lotes_20260920_154650_211744.json` registra duas tentativas.

| Métrica | Antes | Depois |
|---|---:|---:|
| Vetores preenchidos | 125 | 157 |
| Documentos | 51.009 | 51.009 |
| Fragmentos únicos | 185.789 | 185.789 |
| Vínculos | 232.902 | 232.902 |
| Obras / fatos | 60.580 / 60.580 | 60.580 / 60.580 |

`validate_data`: **válido**, todas as inconsistências zeradas, inclusive rótulos
indevidos. Baseline e resultado em `logs/sprint4_008_baseline_20260920.json` e
`logs/sprint4_008_final_20260920.json`. Não houve alteração de fontes, chunks ou rótulos.

## Testes e limites

**84 passed in 6.26s** pelo runner oficial `scripts/testar_sprint3.py`, com banco
PostgreSQL descartável. Testes cobrem manifesto alterado/duplicado, deriva de tokens,
rollback quando o segundo vetor é inválido, falha de checkpoint após a transação,
retomada sem carregar modelo, arquivo ausente/alterado e escape de caminho.
`git diff --check` sem erros. Nenhuma nova dependência foi introduzida.

O ensaio amplia a infraestrutura técnica; não fecha T009/T011/T013/T014 da feature
007, nem autoriza inferir relevância dos 32 novos chunks pelos julgamentos anteriores.
Pacotes antigos mantêm o universo original; nova avaliação exige novo pacote e revisão.
Carga integral, decisão de índice e adjudicação humana continuam pendentes na 007.
Random Forest permanece experimento supervisionado posterior, dependente de rótulos
homologados; ver `../007-piloto-embeddings/random-forest.md`.

## Verificação para convergência

FR-001..FR-007 e SC-001..SC-005 têm evidência acima; os cinco cenários de aceitação
foram conferidos. Plano implementado sem DDL novo, com locks, seleção congelada,
retomada pelo banco e preservação dos quatro princípios constitucionais.

Primeira convergência: 1 achado parcial HIGH em limites de CLI, registrado como
T011 e corrigido via implementação. Três testes adicionais rejeitam batch 0, -1
e 33 antes da conexão. Inventário: 7 requisitos, 5 critérios de sucesso, 5 cenários
de aceitação, 7 decisões técnicas e 4 princípios constitucionais.

## Continuidade e conclusão técnica — 2026-09-23
A [feature 009](../009-conclusao-sprint4/report.md) concluiu a vetorização dos 185.789 chunks elegíveis. Foram preservados os 157 vetores anteriores e gerados 185.632 novos; auditoria integral, 64 recomputações finais em CPU, retomada e busca exata aprovadas. Nenhuma origem/rótulo foi homologada automaticamente. Os registros anteriores deste documento descrevem suas respectivas etapas históricas.
