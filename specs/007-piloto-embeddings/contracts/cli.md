# Contrato CLI proposto para a primeira etapa

| Operação | Efeito | Critério |
|---|---|---|
| `python scripts/auditar_tokens_sprint4.py --candidato e5\|gte` | Leitura somente do banco e tokenizer fixado; relatório local | Não trunca nem atualiza tabelas |
| `python scripts/piloto_embeddings_sprint4.py` | Inferência estratificada e validação em leitura | Sem escrita no banco |
| `python scripts/piloto_embeddings_sprint4.py --write` | Piloto vetorial após gates e testes | Commit por fragmento e manifesto; sem overwrite incompatível |

As três operações estão implementadas. A carga integral e o índice pertencem a uma etapa posterior, após avaliação de qualidade.

## Continuação de 2026-09-19

- `piloto_embeddings_sprint4.py --por-estrato 8 --write`: piloto limitado a 1..16
  conteúdos por ano/base/origem, deduplicado, mais caso de borda. Default continua 1.
  Mede tokenização/inferência, vazão, RSS e pico de working set no Windows.
- `avaliar_busca_sprint4.py --ano 2025 --k 5`: seis consultas exploratórias, somente
  leitura, mesmo modelo/revisão, busca cosseno exata. `--consulta` aceita uma consulta;
  `--origem` separa original/ficha sintética/não confirmada. Ano padrão 2025.
- A busca retorna conteúdos únicos e ocorrências com documento, fato, posição e offsets.
  O universo é apenas o subconjunto vetorizado compatível com os filtros, não o corpus total.
- Relatório e pacote de revisão com textos ficam em `logs/` ignorado pelo Git.
  `--julgamentos caminho.json` exige a mesma assinatura de corpus, consultas idênticas,
  revisor identificado e confirmação de revisão integral do universo. Relevantes são
  IDs únicos do universo. Consulta sem relevante recebe recall indefinido, não sucesso.
- Métricas por consulta: precision@k, recall@k e reciprocal rank@k. Nenhuma métrica
  sem julgamento; nenhuma aprovação automática de escala ou inferência de label_risco.

## Benchmark e autoria da revisão

- `benchmark_embeddings_sprint4.py --container <nome> [--por-faixa 8] [--repeticoes 3]`:
  transação somente leitura e snapshot consistente, auditoria integral por tokenizer
  GTE fixado, amostra determinística por comprimento, memória, projeção ponderada e
  inspeção do volume. Limites: 2..16 exemplos/faixa, 2..5 repetições; faixas com menos
  exemplos usam todos. Excedente de janela interrompe; nenhum truncamento/escrita.
- Julgamentos exigem `tipo_revisao` explícito (`humana` ou `assistida_ia`). Ausência
  é erro. Métricas assistidas recebem estado próprio e não equivalem a homologação.
- O pacote inicial não preenchido contém `tipo_revisao: null`; não pode gerar métricas.
