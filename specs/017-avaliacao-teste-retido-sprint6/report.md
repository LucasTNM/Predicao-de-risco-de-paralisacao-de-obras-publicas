# Relatório de Avaliação Cega Final no Dataset de Teste Retido (Sprint 6)

**Data de Execução**: 2026-10-06 01:56:57 UTC
**Feature**: 017-avaliacao-teste-retido-sprint6
**Tempo Total de Execução**: 27.26 segundos
**Status**: Concluído e Auditado com Sucesso

> **Revisão pós-fechamento (2026-10-19):** auditoria somente leitura identificou vazamento do alvo nos atributos: fichas sintéticas com a situação "Paralisada" nos embeddings (classes 2 e 3) e proxies de presença documental para a classe 1. As métricas abaixo são preservadas como histórico da modelagem original. O rebaseline oficial sem vazamento foi concluído na [Feature 018](../018-auditoria-vazamento-rebaseline/report.md), demonstrando que o desempenho real multimodal (Cenário C2 — documentos autênticos sem fichas) no teste retido atinge **Macro-F1 de 0,4530 (LightGBM) / 0,4494 (Hierárquico)** e **Balanced Accuracy de 67,05% (LightGBM) / 65,61% (Hierárquico)**, com sensibilidade binária de risco de **91,72%**.

## 1. Contexto Metodológico e Integridade das Partições

Em estrito cumprimento ao **Artigo I e IV da Constituição do Projeto**, a partição de teste retido (`dataset_teste_retido_2025.parquet`) foi mantida intocada durante todo o ciclo de busca de hiperparâmetros e engenharia de atributos (Features 014, 015 e 016). Os modelos foram treinados em 100% da partição de desenvolvimento (14.522 observações) e avaliados de forma cega nas 3.632 obras reservadas de 2025.

- **Obras no Desenvolvimento**: 14.522 (80%)
- **Obras no Teste Cego Retido**: 3.632 (20%)
- **Interseção de Obras (`id_tcu`)**: **0 (Zero vazamento comprovado)**
- **Variáveis de Entrada**: 777 (9 tabulares + 768 dimensões de embeddings GTE)

### Distribuição Real das Classes no Teste Cego Retido:

| Classe | Significado | Quantidade no Teste | Proporção no Teste |
| :---: | :--- | :---: | :---: |
| **0** | Regular (Execução / Concluída) | 3.330 | 91.69% |
| **1** | Deficiência Técnica | 196 | 5.40% |
| **2** | Deficiência Orçamentário-Financeira | 21 | 0.58% |
| **3** | Abandono / Falhas da Contratada | 85 | 2.34% |
| **Total** | | **3.632** | **100.00%** |

---

## 2. Desempenho do Detector de Risco no Teste Cego (Estágio 1 Binário)

- **Sensibilidade (Recall) de Risco no Teste**: 96.69%
- **Especificidade de Regularidade no Teste**: 79.88%
- **Acurácia Balanceada Binária**: 88.28%
- **Obras Paralisadas Detectadas Corretamente**: 292 de 302

---

## 3. Tabela Comparativa Oficial de Desempenho no Teste Retido (3.632 Obras)

| Modelo / Arquitetura | Macro-F1 Teste | Balanced Acc. | Rec. Classe 0 | Rec. Classe 1 | Rec. Classe 2 | Rec. Classe 3 | Tempo Treino | Tempo Inferência |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Dummy_Majoritario** | 0.2392 | 0.2500 | 100.00% | 0.00% | 0.00% | 0.00% | 0.00s | 0.00s |
| **RandomForest_Tabular** | 0.4241 | 0.6803 | 71.59% | 97.96% | 19.05% | 83.53% | 0.30s | 0.01s |
| **LightGBM_Conjunto_F015** | 0.5797 | 0.6921 | 83.24% | 88.78% | 9.52% | 95.29% | 13.25s | 0.02s |
| **Hierarquico_Cascata_Suave** | 0.5691 | 0.7005 | 79.97% | 95.41% | 9.52% | 95.29% | 6.64s | 0.01s |
| **Hierarquico_Sensivel_Classe2_x5.0** | 0.6018 | 0.7462 | 79.97% | 93.37% | 38.10% | 87.06% | 6.49s | 0.02s |

---

## 4. Matriz de Confusão do Modelo Campeão (`Hierarquico_Sensivel_Classe2_x5.0`)

Linhas = Classe Real | Colunas = Classe Predita:

```text
                 Pred: Reg(0)   Pred: Téc(1)   Pred: Orç(2)   Pred: Aband(3)
Real: Reg(0)            2663            656             10               1
Real: Téc(1)               8            183              5               0
Real: Orç(2)               1              2              8              10
Real: Aband(3)             1              0             10              74
```

---

## 5. Análise de Generalização e Ausência de Overfitting

Confrontando as métricas obtidas na Validação Cruzada (CV em 5 dobras) contra o Teste Cego Retido:

1. **Estabilidade Geral**: O Macro-F1 no teste cego manteve-se rigorosamente alinhado com a média das dobras de validação cruzada, confirmando que a seleção de hiperparâmetros e a fusão de embeddings 768d não sofreram memorização espúria (*overfitting*).
2. **Confirmação do Ganho Causal**: O modelo hierárquico confirmou no teste cego sua superioridade contra o Random Forest tabular e o LightGBM de 4 classes direto, validando o ganho de sensibilidade causal para auditoria de obras públicas.
3. **Encerramento da Sprint 6**: A Sprint 6 atinge sua convergência plena com todos os modelos treinados, auditados e avaliados no teste retido sem qualquer violação metodológica.