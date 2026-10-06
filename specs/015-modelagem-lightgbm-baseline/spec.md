# Feature Specification: 015-modelagem-lightgbm-baseline

**Feature Branch**: `015-modelagem-lightgbm-baseline`
**Created**: 2026-10-05
**Status**: Completed
**Input**: Decisão do pesquisador: "manteremos o Random Forest como teste inicial, mas vamos priorizar o LightGBM porque ele é otimizado matematicamente para alta dimensionalidade (vetores de 768 posições). Ele treina até 10x mais rápido e consome uma fração da memória RAM, o que é um requisito não-funcional crítico para a nossa infraestrutura gratuita em nuvem."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Baselines de Referência Inicial: Trivial e Random Forest Tabular (Priority: P1)

Como pesquisador do TCC, desejo treinar um classificador trivial (`DummyClassifier` na classe mais frequente) e um modelo clássico de `RandomForest` utilizando os atributos tabulares/cadastrais e financeiros disponíveis, para estabelecer o piso comparativo de desempenho e mensurar rigorosamente o valor adicionado por abordagens mais complexas e semânticas.

**Why this priority**: Todo avanço científico em aprendizado de máquina supervisionado exige um baseline de referência honesto. O DummyClassifier expõe o viés da classe majoritária (91,7%), enquanto o Random Forest tabular quantifica o poder preditivo estritamente tabular antes da inclusão de embeddings textuais.

**Independent Test**: Pode ser testado executando o treinamento na partição de desenvolvimento (`dataset_treino_dev_2025.parquet`) e verificando se os modelos geram predições válidas com avaliação de acurácia, Macro-F1 e matriz de confusão, demonstrando que o DummyClassifier atinge Macro-F1 próximo de zero para as classes minoritárias.

**Acceptance Scenarios**:
1. **Given** o dataset de desenvolvimento com 14.522 observações rotuladas, **When** o baseline trivial for executado, **Then** ele deve produzir predições da classe 0 para todos os casos, demonstrando que acurácia simples (~91,7%) é uma ilusão metodológica com Macro-F1 inferior a 0,25.
2. **Given** os atributos numéricos (`valor_investimento`, `exec_fisica`, `exec_financeira`, etc.) e categóricos das obras, **When** o Random Forest tabular for ajustado, **Then** suas métricas de validação cruzada devem ser registradas como primeira referência comparativa.

---

### User Story 2 - Modelagem Prioritária com LightGBM para Alta Dimensionalidade (Priority: P1)

Como pesquisador do projeto, desejo implementar um classificador supervisionado baseado em LightGBM capaz de operar sobre a concatenação dos atributos tabulares com o vetor semântico denso de 768 posições (embeddings agregados dos documentos da obra), utilizando divisões baseadas em histogramas e amostragem GOSS, para alcançar treinamento ágil com consumo mínimo de memória RAM compatível com ambientes gratuitos em nuvem.

**Why this priority**: Os 768 atributos contínuos dos embeddings geram uma matriz densa de alta dimensionalidade que impõe gargalos severos de memória e processamento para algoritmos tradicionais baseados em ordenação prévia (como o Random Forest). O LightGBM resolve isso matematicamente com binning de histogramas e GOSS, treinando ordens de magnitude mais rápido e respeitando as restrições da infraestrutura sem custos.

**Independent Test**: Pode ser testado treinando o LightGBM na matriz combinada (tabular + 768d) e verificando que o treinamento completa em tempo reduzido (< 30s) consumindo uma fração de memória RAM, gerando predições e probabilidades para as 4 classes causais.

**Acceptance Scenarios**:
1. **Given** o conjunto de treino com 14.522 obras e 768 dimensões vetoriais por obra, **When** o LightGBM for treinado, **Then** o tempo de execução deve ser substancialmente inferior ao de árvores tradicionais e sem estouro de memória (*out of memory*).
2. **Given** as predições geradas pelo LightGBM, **When** forem confrontadas com o vetor de alvos reais (classes 0, 1, 2 e 3), **Then** as probabilidades estimadas para cada classe devem somar 1.0 por observação e permitir classificação multiclasse determinística.

---

### User Story 3 - Ponderação e Tratamento do Desbalanceamento Severo de Classes (Priority: P1)

Como auditor de dados, desejo que o treinamento dos modelos incorpore estratégias de balanceamento sensíveis ao custo (como ponderação de perda inversamente proporcional à frequência das classes, `class_weight='balanced'`), para que as classes minoritárias críticas (especialmente Classe 2 — Deficiência orçamentário-financeira com apenas 83 casos no treino) não sejam ignoradas pelo algoritmo preditivo.

**Why this priority**: Com 91,7% de obras regulares (Classe 0) e 0,6% de Classe 2, um otimizador padrão minimizador de entropia cruzada prioriza maciçamente a classe 0. A ponderação de classes na função objetivo penaliza erros nas classes raras sem a necessidade de gerar dados sintéticos arriscados no espaço de 768 dimensões.

**Independent Test**: Pode ser testado comparando o LightGBM treinado sem ponderação vs. com ponderação balanceada, verificando aumento substantivo no Recall das classes 1, 2 e 3 e elevação do Macro-F1.

**Acceptance Scenarios**:
1. **Given** a distribuição desbalanceada das classes no treino (13.319 classe 0, 782 classe 1, 83 classe 2, 338 classe 3), **When** a matriz de pesos de classe for aplicada na função de perda do LightGBM, **Then** a taxa de acerto (Recall) da Classe 2 e Classe 3 deve ser superior à do modelo não balanceado.
2. **Given** a restrição constitucional de não contaminação do teste, **When** qualquer ajuste de pesos ou balanceamento for calibrado, **Then** ele deve ser derivado estritamente das frequências da partição de treino, sem utilizar informações do conjunto de teste retido.

---

### User Story 4 - Validação Cruzada Agrupada por Obra e Relatório Comparativo (Priority: P2)

Como cientista de dados, desejo avaliar os modelos por meio de validação cruzada em 5 dobras estratificada por grupos de identidade de obra (`id_tcu`), gerando um relatório comparativo contendo Macro-F1, Balanced Accuracy, Recall por classe, Matriz de Confusão, tempo de processamento e consumo de memória, para embasar a escolha do modelo final com rigor científico.

**Why this priority**: A avaliação deve ser livre de viés de vazamento entre dobras (uma obra nunca pode estar simultaneamente no fold de treino e validação). As métricas agregadas devem evidenciar claramente as vantagens do LightGBM frente ao Random Forest e ao baseline trivial.

**Independent Test**: Pode ser testado gerando as 5 dobras de validação cruzada, executando a avaliação dos modelos e gerando um relatório em formato estruturado (JSON e Markdown) com todas as métricas detalhadas.

**Acceptance Scenarios**:
1. **Given** as 5 dobras de validação cruzada, **When** as partições de cada dobra forem inspecionadas, **Then** a interseção de `id_tcu` entre o treino interno e a validação interna deve ser exatamente zero.
2. **Given** os resultados das avaliações dos três modelos (Dummy, Random Forest, LightGBM), **When** o relatório final for consolidado, **Then** ele deve apresentar tabela comparativa com Macro-F1, Balanced Accuracy, Recall por classe e tempos de computação.

---

## Edge Cases

- **Obras sem documentos (`has_embedding = False`)**: O vetor de 768 posições deve ser preenchido com zeros ou valor neutro, e a flag booleana `has_embedding` deve ser mantida como atributo explícito para o modelo aprender que a ausência documental é uma característica do registro.
- **Classe ultra-minoritária (Classe 2 com 83 casos)**: Na divisão das 5 dobras de validação cruzada agrupada, a distribuição dos 83 casos deve garantir pelo menos 15 casos da Classe 2 em cada dobra de validação.
- **Ambiente restrito sem suporte a DLLs não assinadas (SAC/Windows)**: A implementação do motor de modelagem deve utilizar rotinas nativas de alta compatibilidade (DuckDB para I/O de Parquet e LightGBM Core Booster / NumPy puro para métricas e pré-processamento).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE carregar o dataset `dados_processados/sprint6/dataset_treino_dev_2025.parquet` preservando todos os 14.522 registros, seus atributos tabulares, classes de risco (0, 1, 2, 3) e vetores de embedding de 768 dimensões.
- **FR-002**: O sistema DEVE implementar um classificador de linha de base trivial (`DummyClassifier`) baseado na regra de classe mais frequente.
- **FR-003**: O sistema DEVE implementar o modelo `RandomForestClassifier` como baseline comparativo tabular.
- **FR-004**: O sistema DEVE implementar o modelo `LightGBM` multiclasse configurado com divisão por histogramas, amostragem GOSS e crescimento folha por folha (*leaf-wise*).
- **FR-005**: O sistema DEVE calcular e aplicar ponderação de classes inversamente proporcional às frequências da partição de treino (`pesos_classe = total / (n_classes * frequencias)`).
- **FR-006**: O sistema DEVE implementar particionador de validação cruzada agrupada por `id_tcu` com estratificação aproximada das classes raras (5 dobras).
- **FR-007**: O sistema DEVE calcular para cada modelo as métricas: Macro-F1, Balanced Accuracy, Precision/Recall por classe, Matriz de Confusão e tempo de treinamento em segundos.
- **FR-008**: O sistema DEVE persistir os resultados comparativos em artefatos auditáveis (JSON e relatório em Markdown na pasta da spec).

---

## Non-Functional Requirements

- **NFR-001 (Eficiência de Memória)**: O pipeline completo de treino do LightGBM com atributos tabulares + 768 dimensões não deve ultrapassar 2 GB de consumo de RAM.
- **NFR-002 (Velocidade de Execução)**: O tempo total de treinamento de uma rodada do LightGBM em 14.522 observações de 768 dimensões deve ser inferior a 60 segundos em CPU padrão.
- **NFR-003 (Reprodutibilidade)**: Toda divisão de folds, inicialização e treinamento deve fixar a semente aleatória (`seed = 42`).
- **NFR-004 (Independência de Teste)**: O arquivo `dataset_teste_retido_2025.parquet` não deve ser acessado ou modificado durante esta fase de desenvolvimento e validação cruzada interna.
