# Feature Specification: 017-avaliacao-teste-retido-sprint6

**Feature Branch**: `017-avaliacao-teste-retido-sprint6`
**Created**: 2026-10-05
**Status**: Completed
**Input**: Solicitação do usuário: "Execute a validação e qualquer atividade que for fazer use o speckit", formalizando a avaliação cega final da Sprint 6 sobre o dataset de teste retido (`dataset_teste_retido_2025.parquet`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auditoria de Não-Vazamento e Preservação do Teste Cego (Priority: P1)

Como auditor de integridade científica do TCC, desejo auditar a partição de teste retido (`dataset_teste_retido_2025.parquet`) antes de qualquer inferência, confirmando que ela contém exatamente 3.632 obras, que os mapeamentos categóricos e imputações numéricas foram calibrados estritamente no conjunto de desenvolvimento, e que a interseção de `id_tcu` com o desenvolvimento é rigorosamente zero, para certificar a legitimidade do teste cego perante a banca.

**Why this priority**: A validade científica de todo o projeto depende da ausência de contaminação informacional (*data leakage*) entre as partições. A confirmação de não-vazamento antes da inferência garante conformidade absoluta com o Princípio I e IV da Constituição.

**Independent Test**: Pode ser testado verificando se os identificadores únicos de obra no teste não constam no conjunto de desenvolvimento (`len(set_dev & set_test) == 0`) e se o hash do arquivo de teste corresponde ao manifesto oficial da Feature 014.

**Acceptance Scenarios**:
1. **Given** os arquivos `dataset_treino_dev_2025.parquet` (14.522) e `dataset_teste_retido_2025.parquet` (3.632), **When** for calculada a interseção de `id_tcu`, **Then** a interseção deve ser exatamente de zero elementos.
2. **Given** os atributos do conjunto de teste, **When** as transformações de entrada forem aplicadas, **Then** nenhuma informação estatística do teste (média, mediana, distribuição de classes) deve ser utilizada para ajustar o pré-processamento.

---

### User Story 2 - Treinamento Integral no Desenvolvimento e Inferência Cega no Teste (Priority: P1)

Como pesquisador do projeto, desejo treinar os modelos representativos desenvolvidos na Sprint 6 em 100% da base de desenvolvimento (14.522 obras) e executar a predição cega sobre as 3.632 obras reservadas de teste, avaliando:
1. `Dummy_Majoritario` (Linha de base trivial)
2. `RandomForest_Tabular` (Baseline tabular)
3. `LightGBM_Conjunto_F015` (Modelo de 4 classes da Feature 015)
4. `Hierarquico_Cascata_Suave` (Modelo em dois estágios com probabilidades conjuntas)
5. `Hierarquico_Sensivel_Classe2_x5.0` (Modelo campeão da Feature 016)

**Why this priority**: O treinamento com todo o conjunto de desenvolvimento maximiza o uso dos dados rotulados disponíveis, e a inferência no teste reservado mede a capacidade real de generalização para obras nunca vistas no mundo real.

**Independent Test**: Pode ser testado executando o pipeline de inferência e confirmando que cada modelo produz predições válidas para todas as 3.632 observações com cálculo de matriz de confusão e métricas multiclasse.

**Acceptance Scenarios**:
1. **Given** as 3.632 observações do teste retido (3.330 regulares, 196 técnicas, 21 orçamentárias e 85 abandono), **When** os modelos gerarem as predições, **Then** as métricas de Macro-F1, Balanced Accuracy, Precision/Recall por classe e Matriz de Confusão 4x4 devem ser computadas para cada um.
2. **Given** o modelo hierárquico campeão (`Hierarquico_Sensivel_Classe2_x5.0`), **When** avaliado no teste retido, **Then** ele deve confirmar a superação da linha de base trivial e do Random Forest, preservando capacidade de detecção da Classe 2.

---

### User Story 3 - Análise de Estabilidade e Generalização (CV vs. Teste Cego) (Priority: P2)

Como cientista de dados, desejo confrontar as métricas obtidas na validação cruzada interna (Features 015 e 016) com as métricas observadas no teste cego retido, quantificando o grau de generalização e demonstrando ausência de sobreajuste (*overfitting*), gerando relatório auditável em Markdown e manifesto JSON para consolidação final da Sprint 6.

**Why this priority**: A consistência entre a validação cruzada interna e o teste cego externo comprova a robustez metodológica do pipeline preditivo e encerra formalmente os objetivos de modelagem da dissertação.

**Independent Test**: Pode ser testado gerando tabela comparativa com o delta percentual entre métricas OOF (CV interna) e métricas de teste retido.

**Acceptance Scenarios**:
1. **Given** os resultados da validação cruzada e do teste retido, **When** o relatório final for consolidado, **Then** ele deve apresentar a comparação direta de Macro-F1, Balanced Accuracy e Recall das 4 classes.
2. **Given** a execução completa da validação, **When** o script finalizar, **Then** deve gravar `benchmark_teste_retido.json` e `report.md` com hashes de integridade.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE carregar o dataset `dataset_teste_retido_2025.parquet` utilizando DuckDB, validando a cardinalidade exata de 3.632 observações.
- **FR-002**: O sistema DEVE validar programaticamente que `len(set(dev_id_tcu) & set(test_id_tcu)) == 0`.
- **FR-003**: O sistema DEVE treinar os modelos em 100% dos dados de `dataset_treino_dev_2025.parquet` utilizando semente determinística 42.
- **FR-004**: O sistema DEVE aplicar os mesmos mapeamentos categóricos derivados do conjunto de desenvolvimento aos dados de teste.
- **FR-005**: O sistema DEVE calcular para todos os modelos no conjunto de teste: Macro-F1, Balanced Accuracy, Precision/Recall por classe, Matriz de Confusão 4x4 e métricas do detector binário (Sensibilidade de Risco).
- **FR-006**: O sistema DEVE gerar relatório em Markdown (`report.md`) e manifesto JSON (`benchmark_teste_retido.json`) na pasta da spec.

### Non-Functional Requirements

- **NFR-001 (Tempo de Execução)**: O treinamento e a inferência no teste retido para todos os 5 modelos devem concluir em menos de 60 segundos no total.
- **NFR-002 (Integridade dos Dados)**: O arquivo Parquet de teste não deve ser modificado ou regravado.
- **NFR-003 (Reprodutibilidade)**: Semente pseudo-aleatória 42 estritamente fixada em todos os modelos.
