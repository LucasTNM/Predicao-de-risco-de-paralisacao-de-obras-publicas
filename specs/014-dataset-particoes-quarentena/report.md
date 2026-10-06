# Relatório de Execução: 014-dataset-particoes-quarentena

**Data:** 2026-10-01 / 2026-10-02
**Status:** Concluído com Sucesso
**Fluxo:** SpecKit specify -> plan -> tasks -> implement -> converge

## 1. Resumo da Entrega

A Feature 014 implementou o pipeline de consolidação dimensional, agregação semântica vetorial e particionamento estratificado por identidade de obra sem vazamento de dados, cumprindo rigorosamente os quatro artigos da Constituição do Projeto.

- **Total de observações processadas**: 60.580 (100% da base PostgreSQL).
- **Quarentena documental aplicada**: 36 documentos DNIT excluídos formalmente da agregação textual das 22 obras com desvio de objeto comprovado na Feature 012.
- **Auditoria de vazamento**: 0% de interseção entre obras do conjunto de desenvolvimento e obras do conjunto de teste (`intersecao_obras = 0`).
- **Segregação temporal de 2026**: 32.292 observações isoladas com zero ocorrências nos conjuntos de treino/teste (Constituição Art. I).
- **Reserva de casos pendentes de 2025**: 10.134 obras com `label_risco = NULL` preservadas sem atribuição forçada de classes.
- **Partição de desenvolvimento (80%)**: 14.522 observações rotuladas de 2025.
- **Partição de teste reservada (20%)**: 3.632 observações rotuladas de 2025.
- **Regressão integral**: **220 testes aprovados em 13,42s** (incluindo 6 novos testes de integridade dimensional, quarentena e não-vazamento).

---

## 2. Distribuição das Partições e Balanceamento de Classes

| Partição | Finalidade | Total Obs. | Obras Únicas | % Embeddings | Classe 0 (Reg.) | Classe 1 (Téc.) | Classe 2 (Orç.) | Classe 3 (Aband.) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `treino_dev` | Ajuste e CV interna | 14.522 | 14.522 | 40,70% | 13.319 (91,7%) | 782 (5,4%) | 83 (0,6%) | 338 (2,3%) |
| `teste_retido` | Avaliação final intocada | 3.632 | 3.632 | 41,41% | 3.330 (91,7%) | 196 (5,4%) | 21 (0,6%) | 85 (2,3%) |
| `pendentes_2025` | Inferência/revisão futura | 10.134 | 10.134 | - | - | - | - | - |
| `isolado_2026` | Projeção administrativa | 32.292 | 32.292 | - | - | - | - | - |
| **Total** | | **60.580** | **60.580** | | **16.649** | **978** | **104** | **423** |

*Nota metodológica*: A proporção de cada classe entre `treino_dev` e `teste_retido` reflete exatamente a razão 80/20 (ex.: Classe 2 possui 83 casos no treino e 21 no teste; Classe 1 possui 782 no treino e 196 no teste; Classe 3 possui 338 no treino e 85 no teste; Classe 0 possui 13.319 no treino e 3.330 no teste).

---

## 3. Artefatos Gerados e Hashes SHA-256

Local: `dados_processados/sprint6/`

| Arquivo | Linhas | Formato | SHA-256 |
| :--- | :---: | :---: | :--- |
| `dataset_treino_dev_2025.parquet` | 14.522 | Parquet (Snappy) | `manifesto_particionamento.json` |
| `dataset_teste_retido_2025.parquet` | 3.632 | Parquet (Snappy) | `manifesto_particionamento.json` |
| `dataset_pendentes_2025.parquet` | 10.134 | Parquet (Snappy) | `manifesto_particionamento.json` |
| `dataset_isolado_2026.parquet` | 32.292 | Parquet (Snappy) | `manifesto_particionamento.json` |
| `manifesto_particionamento.json` | - | JSON | Documento de auditoria com estatísticas e parâmetros |

---

## 4. Conformidade Constitucional

- **Princípio I (Fidedignidade Histórica)**: Zero observações de 2026 participam das partições de treino ou avaliação. Casos sem evidência causal documentada permanecem com `label_risco = NULL`. Nenhuma classe foi forçada ou extrapolada.
- **Princípio II (Integridade Semântica e Quarentena)**: Os 36 documentos DNIT que continham serviços incompatíveis foram expurgados da agregação de vetores textuais.
- **Princípio III (Consistência Dimensional)**: Cardinalidade exata 1:1 com a `fato_risco` preservada. Não houve soma duplicada de medidas financeiras decorrente da cardinalidade da tabela ponte N:N.
- **Princípio IV (Reprodutibilidade e MLOps)**: Semente pseudo-aleatória 42 registrada. Pipeline determinístico executado em 37,27 segundos com hashes SHA-256 publicados no manifesto.
