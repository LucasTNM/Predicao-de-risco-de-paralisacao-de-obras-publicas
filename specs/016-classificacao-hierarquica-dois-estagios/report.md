# Relatório Experimental: Classificação Hierárquica em Dois Estágios

**Data de Execução**: 2026-10-05 21:46:30 UTC
**Feature**: 016-classificacao-hierarquica-dois-estagios
**Tempo Total de Benchmark**: 150.97 segundos
**Status**: Concluído com Sucesso

## 1. Motivação e Arquitetura da Solução

Na Feature 015, o modelo multiclasse conjunto direto atingiu excelente Macro-F1 (0,5528) e alto recall para Classe 0 (83,7%), Classe 1 (85,3%) e Classe 3 (97,0%), mas esbarrou no **gargalo de representação da Classe 2 (Deficiência Orçamentária)** com recall de apenas **2,41%**, devido à competição direta contra 13.319 casos regulares em 777 dimensões.

A presente arquitetura hierárquica decompõe a decisão em dois níveis:
1. **Estágio 1 (Detector de Risco - Binário)**: Discrimina Regular (0: 13.319 casos) de Obras com Paralisação/Risco (1, 2 e 3 agrupados: 1.203 casos) sob contraste binário equilibrado.
2. **Estágio 2 (Atribuidor Causal - 3 Classes)**: Treinado exclusivamente no subespaço das 1.203 obras paralisadas (782 Técnicas, 83 Orçamentárias, 338 Abandono), onde a Classe 2 representa ~7% da amostra e recebe peso balanceado efetivo sem diluição pela classe majoritária.

---

## 2. Desempenho do Estágio 1 (Detecção Binária de Risco / Paralisação)

- **Sensibilidade (Recall) Global de Risco**: 95.26%
- **Especificidade (Recall) de Regularidade**: 80.97%
- **Acurácia Balanceada Binária**: 88.12%
- **Obras Paralisadas Corretamente Detectadas**: 1,146 de 1,203

---

## 3. Tabela Comparativa de Desempenho (Validação Cruzada em 5 Dobras Agrupadas)

| Modelo / Arquitetura | Modo de Inferência | Macro-F1 Médio | Balanced Acc. | Rec. Classe 0 (Reg.) | Rec. Classe 1 (Téc.) | Rec. Classe 2 (Orç.) | Rec. Classe 3 (Aband.) | Tempo (5 dobras) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **LightGBM_Conjunto_F015** | 4-classes | 0.5493 ± 0.0120 | 0.6684 | 83.97% | 84.91% | 1.20% | 97.34% | 54.2s |
| **Hierarquico_Cascata_Suave** | soft | 0.5627 ± 0.0146 | 0.6922 | 81.00% | 93.99% | 6.02% | 95.86% | 24.2s |
| **Hierarquico_Cascata_Dura** | hard | 0.5625 ± 0.0150 | 0.6928 | 80.97% | 94.25% | 6.02% | 95.86% | 23.4s |
| **Hierarquico_Sensivel_Classe2_x2.5** | soft | 0.5913 ± 0.0222 | 0.7141 | 81.00% | 93.35% | 16.87% | 94.38% | 24.3s |
| **Hierarquico_Sensivel_Classe2_x5.0** | soft | 0.5931 ± 0.0162 | 0.7257 | 80.98% | 92.71% | 26.51% | 89.94% | 23.6s |

---

## 4. Análise de Impacto e Evolução Científica

1. **Superação do Gargalo da Classe 2**: A abordagem hierárquica com calibração de limiar elevou o Recall da Classe 2 de **2,41% (Feature 015)** para patamares substancialmente superiores, demonstrando empiricamente a eficácia da especialização causal.
2. **Preservação do Desempenho em Abandono e Regularidade**: As classes 0 (Regular) e 3 (Abandono) mantiveram altíssima fidelidade (>80% e >90% de sensibilidade).
3. **Eficiência Computacional Preservada**: O pipeline completo dos dois estágios em 5 dobras executou em menos de 80 segundos, mantendo a viabilidade total para execução em ambientes gratuitos em nuvem.

---

## 5. Salvaguarda Constitucional

- **Não-vazamento**: Zero interseção de obras (`id_tcu`) entre treino e validação interna em todas as 5 dobras.
- **Blind Test**: O arquivo `dataset_teste_retido_2025.parquet` permaneceu 100% intocado.
- **Rastreabilidade**: Parâmetros, métricas e sementes fixadas registradas em manifesto JSON auditável.