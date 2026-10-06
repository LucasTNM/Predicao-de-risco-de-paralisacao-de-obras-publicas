# Feature Specification: 016-classificacao-hierarquica-dois-estagios

**Feature Branch**: `016-classificacao-hierarquica-dois-estagios`
**Created**: 2026-10-05
**Status**: Completed
**Input**: Próxima etapa recomendada da Sprint 6: implementar abordagem hierárquica em dois estágios (Detecção Binária de Risco seguida de Atribuição Causal Multiclasse) para superar o gargalo de representação da Classe 2 (0,57% da base).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Estágio 1: Detector Binário de Risco de Paralisação (Priority: P1)

Como pesquisador do TCC, desejo treinar um classificador binário especializado com LightGBM para distinguir obras regulares (Classe 0) de obras com paralisação/risco (Classes 1, 2 e 3 agrupadas), utilizando ponderação positiva de escala (`scale_pos_weight`), para maximizar a sensibilidade na identificação de obras problemáticas sem diluir os gradientes causais específicos.

**Why this priority**: No problema global de 4 classes, 83 casos da Classe 2 competem diretamente contra 13.319 casos regulares em 777 dimensões. Ao isolar a decisão de risco em nível binário (13.319 Regulares vs. 1.203 com Paralisação, proporção ~11:1), o modelo aprende uma fronteira de decisão nítida entre normalidade administrativa e anomalia/paralisação.

**Independent Test**: Pode ser testado treinando o classificador binário nas dobras de validação cruzada e avaliando ROC-AUC, PR-AUC, F1-Score binário e matriz de confusão binária 2x2.

**Acceptance Scenarios**:
1. **Given** os rótulos de desenvolvimento com alvos 0, 1, 2 e 3, **When** a binarização for calculada ($y_{bin} = 1$ se $y \in \{1, 2, 3\}$ senão 0), **Then** o conjunto de treino deve apresentar exatamente 13.319 casos negativos (0) e 1.203 casos positivos (1).
2. **Given** o LightGBM binário treinado com atributos híbridos (tabulares + 768d), **When** avaliado nas dobras de teste, **Then** o Recall na classe de risco (positiva) deve ser superior a 85% com PR-AUC bem calibrada.

---

### User Story 2 - Estágio 2: Atribuidor Causal Condicional (Priority: P1)

Como auditor de obras públicas, desejo treinar um classificador multiclasse condicional especializado (Estágio 2) treinado exclusivamente sobre as obras que possuem paralisação documentada (Classes 1, 2 e 3), para discernir entre Deficiência Técnica (1), Deficiência Orçamentário-Financeira (2) e Abandono da Contratada (3) em um subespaço onde a Classe 2 representa ~7% da amostra (e não 0,57%).

**Why this priority**: No subconjunto de 1.203 obras com causa, a distribuição é de 782 técnicas (65,0%), 83 orçamentárias (6,9%) e 338 de abandono (28,1%). A ponderação balanceada neste subespaço confere um peso de ~4.8x para a Classe 2 em vez de ser sufocada pela massa de 13.319 regulares, permitindo ao LightGBM capturar padrões semânticos textuais e financeiros específicos de restrição orçamentária.

**Independent Test**: Pode ser testado treinando o modelo apenas nas observações onde $y \in \{1, 2, 3\}$ e avaliando o Recall individual da Classe 2, comparando com o valor obtido na Feature 015 (2,41%).

**Acceptance Scenarios**:
1. **Given** o subconjunto de obras paralisadas (1.203 no total do treino), **When** o Estágio 2 for ajustado com pesos balanceados condicionais, **Then** as predições no subespaço de causas devem apresentar aumento significativo no Recall da Classe 2 (meta: > 25%).
2. **Given** os atributos híbridos das obras paralisadas, **When** as importâncias forem inspecionadas, **Then** atributos financeiros (`valor_desbloqueado`, `exec_financeira`, embeddings específicos) devem demonstrar maior peso relativo para a Classe 2.

---

### User Story 3 - Inferência Conjunta e Combinação de Probabilidades (Priority: P1)

Como cientista de dados, desejo integrar os dois estágios em um único estimador hierárquico (`TwoStageHierarchicalClassifier`) capaz de operar em modo cascata determinística (*Hard Cascade*) e modo de probabilidade total (*Soft Cascade*):
$$P(Y = 0) = P(\text{Estágio 1} = 0)$$
$$P(Y = c) = P(\text{Estágio 1} = 1) \times P(\text{Estágio 2} = c \mid \text{Risco}), \quad \forall c \in \{1, 2, 3\}$$
para fornecer tanto a classe causal final quanto o vetor calibrado de 4 probabilidades para cada obra.

**Why this priority**: A tomada de decisão prática em auditoria precisa de probabilidades consistentes em $[0, 1]$ somando 1.0 para as 4 classes, além de permitir calibração do limiar operacional de risco de acordo com o custo de fiscalização.

**Independent Test**: Pode ser testado executando a inferência sobre o conjunto completo de desenvolvimento e verificando se todas as predições pertencem a $\{0, 1, 2, 3\}$ e se a matriz de probabilidades tem dimensionalidade $(N, 4)$ com soma unitária por linha.

**Acceptance Scenarios**:
1. **Given** uma matriz de entrada $X$ com observações diversas, **When** `predict_proba(X)` for invocado, **Then** o retorno deve ser um array float32 $(N, 4)$ com todas as linhas somando exatamente 1.0 (tolerância $10^{-5}$).
2. **Given** o estimador hierárquico ajustado, **When** avaliado contra os alvos originais de 4 classes, **Then** as métricas globais de Macro-F1 e Balanced Accuracy devem superar o modelo de estágio único da Feature 015.

---

### User Story 4 - Validação Cruzada Agrupada e Comparativo com Feature 015 (Priority: P2)

Como pesquisador, desejo avaliar a abordagem hierárquica sob o mesmo protocolo estrito de validação cruzada em 5 dobras agrupadas por `id_tcu` utilizado na Feature 015, gerando relatório comparativo detalhado (Macro-F1, Balanced Accuracy, Recall por classe e tempos de computação) para demonstrar com rigor acadêmico o ganho da decomposição hierárquica.

**Why this priority**: A comparabilidade científica exige que as mesmas 5 dobras e as mesmas partições sejam utilizadas. O resultado demonstrará empiricamente a eficácia da abordagem hierárquica para lidar com desbalanceamento severo em dados textuais/tabulares de obras públicas.

**Independent Test**: Pode ser testado executando a CLI `scripts/treinar_hierarquico_sprint6.py` e gerando os artefatos `report.md` e `benchmark_hierarquico_sprint6.json` com confronto direto contra os dados da Feature 015.

**Acceptance Scenarios**:
1. **Given** as 5 dobras de validação cruzada do `StratifiedGroupSplitter`, **When** o modelo hierárquico for avaliado, **Then** o Recall da Classe 2 deve ser superior ao do modelo de estágio único (2,41%).
2. **Given** os resultados consolidados, **When** o relatório for gerado, **Then** ele deve incluir matriz de confusão global 4x4 e comparação direta com o baseline e o modelo conjunto.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE implementar o modelo hierárquico `TwoStageHierarchicalClassifier` composto por:
  - Estágio 1: Classificador binário `BinaryRiskDetector` (LightGBM com `scale_pos_weight`).
  - Estágio 2: Classificador multiclasse `ConditionalCausalClassifier` (LightGBM com pesos balanceados restrito a $y \in \{1, 2, 3\}$).
- **FR-002**: O sistema DEVE suportar dois modos de predição:
  - `hard_cascade`: Decisão booleana no estágio 1 roteia para classe 0 ou para a predição do estágio 2.
  - `soft_cascade`: Probabilidade total marginalizada $P(Y=0) = 1 - P_{risco}$ e $P(Y=c) = P_{risco} \times P_{causa=c}$.
- **FR-003**: O sistema DEVE permitir ajuste de limiar de corte de risco $\theta \in (0, 1)$ no Estágio 1 (padrão 0.50).
- **FR-004**: O sistema DEVE treinar os dois estágios estritamente dentro de cada dobra de treino da validação cruzada, sem qualquer vazamento de informação do conjunto de validação ou do teste retido.
- **FR-005**: O sistema DEVE calcular as métricas completas: Macro-F1, Balanced Accuracy, Precision/Recall por classe, Matriz de Confusão 4x4 e métricas binárias do Estágio 1 (ROC-AUC, Precision, Recall).
- **FR-006**: O sistema DEVE gerar artefatos auditáveis em `specs/016-classificacao-hierarquica-dois-estagios/report.md` e JSON estruturado.

### Non-Functional Requirements

- **NFR-001 (Tempo de Treinamento)**: O treinamento completo dos dois estágios em 5 dobras não deve ultrapassar 120 segundos no total.
- **NFR-002 (Eficiência de Memória)**: O pipeline não deve exceder 1,5 GB de RAM.
- **NFR-003 (Reprodutibilidade)**: Semente pseudo-aleatória 42 estritamente fixada em ambos os estágios e splitters.
- **NFR-004 (Blind Test)**: O dataset reservado `dataset_teste_retido_2025.parquet` permanece intocado.
