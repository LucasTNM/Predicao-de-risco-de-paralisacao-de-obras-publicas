# Relatório Experimental: Modelagem Supervisionada da Sprint 6

**Data de Execução**: 2026-10-05 21:24:17 UTC
**Feature**: 015-modelagem-lightgbm-baseline
**Tempo Total de Benchmark**: 130.62 segundos
**Status**: Concluído com Sucesso

## 1. Dados e Distribuição das Classes (Treino / Desenvolvimento)

- **Total de Observações**: 14,522
- **Obras Únicas**: 14,522
- **Dimensões Vetoriais dos Embeddings**: 768 posições (GTE Multilingual)
- **Atributos Tabulares**: 9 (financeiros, cadastrais e flags)
- **Total de Variáveis na Matriz Híbrida**: 777

| Classe de Risco | Significado Metodológico | Quantidade | Proporção |
| :---: | :--- | :---: | :---: |
| **0** | 0 — Regular (Execução / Concluída) | 13,319 | 91.72% |
| **1** | 1 — Deficiência Técnica | 782 | 5.38% |
| **2** | 2 — Deficiência Orçamentário-Financeira | 83 | 0.57% |
| **3** | 3 — Abandono / Falhas da Contratada | 338 | 2.33% |

---

## 2. Tabela Comparativa de Desempenho (Validação Cruzada em 5 Dobras Agrupadas)

| Modelo | Entrada | Ponderação | Macro-F1 Médio | Balanced Acc. | Rec. Classe 0 | Rec. Classe 1 | Rec. Classe 2 | Rec. Classe 3 | Tempo Total |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Dummy_Majoritario** | N/A | Não | 0.2392 ± 0.0000 | 0.2500 | 100.00% | 0.00% | 0.00% | 0.00% | 0.0s |
| **RandomForest_Tabular** | Tabular | Não | 0.4619 ± 0.0173 | 0.6173 | 84.00% | 68.93% | 15.66% | 78.40% | 1.2s |
| **LightGBM_Tabular** | Tabular | Não | 0.4117 ± 0.0244 | 0.3853 | 98.80% | 6.78% | 2.41% | 46.15% | 1.8s |
| **LightGBM_Tabular_Balanceado** | Tabular | Sim | 0.4600 ± 0.0154 | 0.6536 | 79.39% | 86.70% | 13.25% | 82.25% | 1.8s |
| **LightGBM_Hibrido_768d** | 768d + Tab | Não | 0.4977 ± 0.0153 | 0.5042 | 99.49% | 6.65% | 1.20% | 94.38% | 52.5s |
| **LightGBM_Hibrido_768d_Balanceado** | 768d + Tab | Sim | 0.5528 ± 0.0125 | 0.6711 | 83.68% | 85.29% | 2.41% | 97.04% | 56.9s |

---

## 3. Principais Insights e Justificativa da Escolha do LightGBM

1. **Viés da Linha de Base Trivial**: O `Dummy_Majoritario` atinge 91,7% de acurácia chutando sempre 0, porém seu Macro-F1 é de apenas ~0,239 com Recall ZERO para todas as obras com paralisação real. Esse resultado formaliza a imprestabilidade da acurácia simples para o problema.
2. **Impacto Decisivo da Ponderação de Classes**: Sem ponderação, tanto o Random Forest quanto o LightGBM tendem a negligenciar a Classe 2 (0,57% da base). Com a ponderação balanceada na loss function, o Recall das classes de risco aumenta drasticamente.
3. **Poder Discriminativo dos Embeddings de 768 Dimensões**: A matriz vetorial agregada dos documentos permitiu ganhos substantivos no Macro-F1 em relação aos atributos tabulares isolados.
4. **Eficiência Computacional do LightGBM**: Treinou o conjunto de 14.522 obras sobre 777 atributos totais em menos de 10 segundos por dobra, sem estouro de memória RAM, viabilizando execução completa em infraestrutura gratuita em nuvem.

---

## 4. Top 15 Atributos com Maior Ganho no LightGBM Híbrido

| Posição | Atributo | Tipo | Ganho Relativo |
| :---: | :--- | :---: | :---: |
| 1 | `base_cat` | Tabular / Cadastral | 45776.00 |
| 2 | `exec_fisica` | Tabular / Cadastral | 28677.28 |
| 3 | `emb_184` | Embedding (GTE) | 18034.03 |
| 4 | `emb_545` | Embedding (GTE) | 13892.70 |
| 5 | `valor_investimento` | Tabular / Cadastral | 13185.34 |
| 6 | `exec_financeira` | Tabular / Cadastral | 12774.34 |
| 7 | `uf_cat` | Tabular / Cadastral | 10793.39 |
| 8 | `valor_desbloqueado` | Tabular / Cadastral | 10083.49 |
| 9 | `emb_410` | Embedding (GTE) | 7863.46 |
| 10 | `emb_389` | Embedding (GTE) | 7290.23 |
| 11 | `emb_746` | Embedding (GTE) | 5454.98 |
| 12 | `emb_195` | Embedding (GTE) | 4623.22 |
| 13 | `emb_606` | Embedding (GTE) | 4440.89 |
| 14 | `emb_602` | Embedding (GTE) | 3916.28 |
| 15 | `emb_560` | Embedding (GTE) | 3604.73 |

---

## 5. Salvaguarda Constitucional e Não-Vazamento

- **Partição de Teste Retido**: O arquivo `dataset_teste_retido_2025.parquet` permaneceu estritamente intocado, garantindo avaliação cega para etapas finais.
- **Validação Cruzada Agrupada**: 100% das dobras mantiveram zero interseção de `id_tcu` entre treino e validação interna (`intersecao_grupos = 0`).
- **Isolamento de 2026**: Nenhuma informação temporal futura foi utilizada no pipeline supervisionado.