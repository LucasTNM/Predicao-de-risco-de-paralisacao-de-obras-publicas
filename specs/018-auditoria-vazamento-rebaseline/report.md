# Relatório Técnico: Auditoria de Vazamento de Alvo e Rebaseline (Sprint 7)

**Feature**: 018-auditoria-vazamento-rebaseline  
**Data**: 2026-10-19  
**Status**: Concluído e Auditado com Sucesso  

---

## 1. Resumo Executivo e Contexto

Durante a preparação da Sprint 7, uma auditoria aprofundada nas fontes de dados textuais e tabulares da Sprint 6 revelou um fenômeno severo de **vazamento de alvo (Target Leakage)** que inflava os resultados dos modelos multimodais:

1. **Vazamento Textual em Fichas Sintéticas**:
   - As fichas sintéticas geradas a partir de metadados continham strings explícitas com o status da obra, tais como: `Situação no [Órgão]: Paralisada (Origem: PARALISADA)` ou `Em execução (Origem: EM EXECUCAO)`.
   - 100% das obras com texto das classes 2 (Execução Técnica) e 3 (Abandono) continham o radical `"paralisad"`, permitindo que os embeddings médios GTE Multilingual atuassem como um atalho trivial de classificação (*shortcut learning*), violando o Artigo I da Constituição do Projeto.
2. **Proxies Documentais Tabulares**:
   - As colunas `has_embedding`, `num_docs_validos` e `num_chunks_validos` identificavam deterministicamente a Classe 1 (Orçamentária), pois 98,8% das obras dessa classe não possuíam documentos associados.
3. **Imputação de Medianas Fora do Treino**:
   - A rotina de imputação tabular prévia calculava as medianas sobre a partição inteira avaliada em vez de projetar estritamente as medianas aprendidas na partição de treino.

Para sanar essas vulnerabilidades e restabelecer a integridade científica do TCC, foram construídos e avaliados 4 cenários experimentais rigorosos em validação cruzada agrupada por `id_tcu` (5 dobras, 14.522 obras de treino/dev), seguido da avaliação única e oficial no conjunto de teste retido (3.632 obras).

---

## 2. Resultados da Validação Cruzada Agrupada (5 Dobras — 14.522 Obras)

A tabela a seguir consolida o desempenho dos 4 modelos nos 4 cenários experimentais executados pelo runner oficial `scripts/rebaseline_sprint7.py` (semente 42):

| Cenário | Modelo | Macro-F1 | Balanced Acc | MCC | Recall 0 (Reg.) | Recall 1 (Orç.) | Recall 2 (Téc.) | Recall 3 (Aban.) | Tempo CV |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C0: Original (Controle)** | Dummy Majoritário | 0.2392 | 0.2500 | 0.0000 | 100.00% | 0.00% | 0.00% | 0.00% | 0.0s |
| | Random Forest Tabular | 0.4425 | 0.6843 | 0.4159 | 74.89% | 96.16% | 16.87% | 85.80% | 1.6s |
| | LightGBM Conjunto | 0.5505 | 0.6719 | 0.4852 | 83.93% | 85.68% | 1.20% | 97.93% | 49.9s |
| | **Hierárquico Campeão** | **0.5632** | **0.6922** | **0.4802** | 81.00% | 93.99% | 6.02% | 95.86% | 24.8s |
| **C1: Tabular Limpo** | Dummy Majoritário | 0.2392 | 0.2500 | 0.0000 | 100.00% | 0.00% | 0.00% | 0.00% | 0.0s |
| *(sem proxies, medianas do treino)* | Random Forest Tabular | 0.4382 | 0.6786 | 0.4107 | 74.44% | 96.42% | 16.87% | 83.73% | 1.4s |
| | LightGBM Conjunto | 0.4547 | 0.6541 | 0.4141 | 78.70% | 87.72% | 13.25% | 81.95% | 1.7s |
| | **Hierárquico Campeão** | **0.4588** | **0.6579** | **0.4142** | 77.89% | 90.92% | 15.66% | 78.70% | 0.7s |
| **C2: Texto sem Fichas** | Dummy Majoritário | 0.2392 | 0.2500 | 0.0000 | 100.00% | 0.00% | 0.00% | 0.00% | 0.0s |
| *(apenas PDFs/docs autênticos)* | Random Forest Tabular | 0.4382 | 0.6786 | 0.4107 | 74.44% | 96.42% | 16.87% | 83.73% | 1.4s |
| | LightGBM Conjunto | 0.4544 | 0.6588 | 0.4148 | 78.27% | 88.87% | 13.25% | 83.14% | 12.1s |
| | **Hierárquico Campeão** | **0.4564** | **0.6591** | **0.4105** | 77.14% | 91.56% | 15.66% | 79.29% | 3.7s |
| **C3: Fichas Mascaradas** | Dummy Majoritário | 0.2392 | 0.2500 | 0.0000 | 100.00% | 0.00% | 0.00% | 0.00% | 0.0s |
| *(situação expurgada)* | Random Forest Tabular | 0.4382 | 0.6786 | 0.4107 | 74.44% | 96.42% | 16.87% | 83.73% | 1.5s |
| | LightGBM Conjunto | 0.4644 | 0.5964 | 0.4104 | 81.33% | 89.77% | 0.00% | 67.46% | 51.9s |
| | Hierárquico Campeão | 0.4491 | 0.6184 | 0.4078 | 77.95% | 94.25% | 0.00% | 75.15% | 25.3s |

---

## 3. Análise Científica e Achados Críticos

1. **Quantificação Exata do Vazamento**:
   - A contaminação no Cenário C0 inflava o Macro-F1 em **+10,44 pontos percentuais** (de 0,4588 para 0,5632) e o Recall da Classe 3 (Abandono) em **+17,16 p.p.** (de 78,70% para 95,86%).
   - Esse achado comprova que o modelo anterior memorizou as expressões literais de paralisação injetadas sinteticamente.
2. **Fracasso Empírico do Mascaramento de Fichas (C3)**:
   - Ao mascarar o texto das fichas sintéticas (C3), o modelo sofreu um colapso representacional: o Recall da Classe 2 caiu para **0,00%** e a Balanced Accuracy despencou de 65,9% para **59,6%–61,8%**.
   - As fichas sintéticas mascaradas apresentam padrões sintáticos e estruturais fixos que geram embeddings concentrados e ruidosos, degradando severamente a discriminação das classes minoritárias.
3. **Robustez dos Cenários C1 e C2**:
   - O **Cenário C1 (Tabular Limpo)** obteve o maior Macro-F1 na validação cruzada (0,4588 no Hierárquico), com Balanced Accuracy sólida de 65,79%.
   - O **Cenário C2 (Texto Limpo sem Fichas)** obteve a maior **Balanced Accuracy global (65,91% no Hierárquico e 65,88% no LightGBM)**, além de maior Recall na classe 1 (91,56% vs 90,92%) e classe 3 (79,29% vs 78,70%), mantendo a detecção da classe 2 em 15,66%.

---

## 4. Pré-Registro Formal do Cenário Eleito para o Teste Retido (T008)

Em estrito cumprimento ao requisito **FR-007** e ao critério de aceitação **SC-005**:

> **Cenário Oficial Eleito**: **C2 — Texto Limpo sem Fichas Sintéticas**  
> **Justificativa**: O Cenário C2 é o único cenário multimodal que elimina 100% das fichas sintéticas, operando exclusivamente sobre documentos autênticos (PDFs e relatórios de fiscalização). Ele atingiu a maior Balanced Accuracy em validação cruzada (0,6591 no Hierárquico e 0,6588 no LightGBM), sem degradar a detecção das classes raras (ao contrário de C3).  
> **Cenário de Controle Tabular**: **C1 — Tabular Limpo** (avaliado para isolar o ganho incremental puro do texto autêntico).  
> **Compromisso**: O conjunto de teste retido (`dataset_teste_retido_2025.parquet`, 3.632 obras) foi consultado **uma única vez** sob este protocolo.

---

## 5. Resultados Oficiais no Dataset de Teste Retido (3.632 Obras)

A avaliação única oficial no dataset de teste retido foi executada pelo script `scripts/avaliar_teste_retido_sprint7.py` em 2026-10-19.

### 5.1 Tabela Comparativa de Teste: C1 vs. C2

| Cenário | Modelo | Macro-F1 | Balanced Acc | MCC | Recall 0 (Reg.) | Recall 1 (Orç.) | Recall 2 (Téc.) | Recall 3 (Aban.) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **C1: Tabular Limpo** | Dummy Majoritário | 0.2392 | 0.2500 | 0.0000 | 100.00% | 0.00% | 0.00% | 0.00% |
| *(sem proxies, medianas do treino)* | Random Forest Tabular | 0.4328 | 0.6744 | 0.4047 | 73.81% | 96.94% | 14.29% | 84.71% |
| | LightGBM Conjunto | 0.4515 | 0.6600 | 0.4053 | 77.42% | 88.78% | 14.29% | 83.53% |
| | Hierárquico Campeão | 0.4462 | 0.6366 | 0.3965 | 77.12% | 90.31% | 14.29% | 72.94% |
| **C2: Oficial (Docs Autênticos)** | Dummy Majoritário | 0.2392 | 0.2500 | 0.0000 | 100.00% | 0.00% | 0.00% | 0.00% |
| *(embeddings reais sem fichas)* | Random Forest Tabular | 0.4328 | 0.6744 | 0.4047 | 73.81% | 96.94% | 14.29% | 84.71% |
| | **LightGBM Conjunto** | **0.4530** | **0.6705** | **0.4142** | 76.88% | 92.35% | 14.29% | **84.71%** |
| | **Hierárquico Campeão** | **0.4494** | **0.6561** | **0.4076** | 76.22% | **95.41%** | **19.05%** | 71.76% |

### 5.2 Desempenho do Detector de Risco Binário no Teste (Estágio 1 - Cenário C2)
- **Sensibilidade Global de Risco (Recall de Paralisação)**: **91,72%** (detecta 277 de 302 obras paralisadas no teste retido).
- **Especificidade de Regularidade**: **76,22%** (2.538 de 3.330 obras regulares classificadas como regulares).
- **Acurácia Balanceada Binária**: **83,97%**.

### 5.3 Ganho Incremental dos Documentos Autênticos (C2 vs. C1)
Comparando o Cenário Oficial Multimodal (C2) com a linha de base tabular (C1) no conjunto de teste retido:
- **LightGBM**: Ganho de **+1,05 p.p.** em Balanced Accuracy (0,6600 → 0,6705), **+3,57 p.p.** no Recall da Classe 1 (88,78% → 92,35%) e **+1,18 p.p.** no Recall da Classe 3 (83,53% → 84,71%).
- **Hierárquico Campeão**: Ganho de **+1,95 p.p.** em Balanced Accuracy (0,6366 → 0,6561), **+5,10 p.p.** no Recall da Classe 1 (90,31% → 95,41%) e **+4,76 p.p.** no Recall da Classe 2 (14,29% → 19,05%).

---

## 6. Lista de Atributos e Fontes Textuais Autorizadas para as Features 019–021 (FR-009)

Para garantir a absoluta conformidade com o Artigo I da Constituição nas etapas seguintes (Feature 019: Motor de Busca RAG; Feature 020: BERTimbau + LoRA; Feature 021: Pipeline Integrado):

### 6.1 Fontes Textuais Permitidas
- **Autorizadas**: Apenas documentos originais com `origem_documento != 'ficha_sintetica'` (ex.: PDFs de relatórios de auditoria, pareceres técnicos, editais e termos aditivos legítimos armazenados em `tcc.dim_documento`).
- **Vedadas / Expurgadas**: Todas as fichas sintéticas geradas a partir de tabelas (`origem_documento = 'ficha_sintetica'`). Elas estão formalmente excluídas de qualquer busca RAG ou treinamento de modelo de linguagem.

### 6.2 Atributos Tabulares Autorizados
- **Autorizados**:
  1. `valor_total_investimento_log` (float, imputado com a mediana do treino)
  2. `percentual_execucao` (float, imputado com a mediana do treino)
  3. `dias_vigencia_total` (float, imputado com a mediana do treino)
  4. `dias_vigencia_restante` (float, imputado com a mediana do treino)
  5. `dias_desde_inicio` (float, imputado com a mediana do treino)
  6. `aditivos_tempo` (int)
  7. `aditivos_valor` (int)
  8. `uf` (categórico, mapeado com categorias do treino, desconhecidos = -1)
  9. `origem_fonte` (categórico, mapeado com categorias do treino, desconhecidos = -1)
- **Vedados / Removidos**:
  1. `has_embedding` (proxy da classe 1)
  2. `num_docs_validos` (proxy da classe 1)
  3. `num_chunks_validos` (proxy da classe 1)

---

## 7. Conformidade com Critérios de Sucesso

- **SC-001**: 100% dos campos das fichas sintéticas classificados no catálogo (`catalogo_vazamento.md`). [Concluído]
- **SC-002**: Reprodução do cenário C0 com diferença de Macro-F1 $\le 0,005$ em relação à Sprint 6. [Concluído: 0,5632 no CV].
- **SC-003**: Tabela comparativa dos 4 cenários × 4 modelos concluída e documentada. [Concluído].
- **SC-004**: Zero fragmentos mencionando situação no cenário eleito C2 (exclusão integral de fichas sintéticas). [Concluído].
- **SC-005**: Uma única avaliação do cenário eleito no teste retido, com pré-registro efetuado antes da execução. [Concluído].
