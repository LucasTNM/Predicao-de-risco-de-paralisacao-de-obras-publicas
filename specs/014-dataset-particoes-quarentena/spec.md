# Feature Specification: 014-dataset-particoes-quarentena

**Feature Branch**: `014-dataset-particoes-quarentena`
**Created**: 2026-10-01
**Status**: Completed
**Input**: User description: "Especificar e implementar a Feature 014 (Preparação do Dataset, Particionamento por Obra sem Vazamento e Quarentena Documental) via SpecKit"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extração tabular e agregação vetorial com quarentena documental (Priority: P1)

Como pesquisador de ciência de dados do TCC, desejo extrair um conjunto de dados consolidado no nível de grão de observação de obra/data-base para o corte histórico de 2025 a partir do banco PostgreSQL, agregando os atributos cadastrais/financeiros e os embeddings textuais dos documentos válidos da obra, excluindo expressamente os documentos identificados na quarentena lógica de incompatibilidade (36 vínculos DNIT da Feature 012), para dispor de atributos preditivos limpos e fidedignos sem distorção informacional.

**Why this priority**: A modelagem supervisionada (Random Forest e modelos subsequentes) requer atributos consolidados no nível da obra e vetores representativos dos textos originais. Sem o expurgo dos documentos com desvio de identidade e sem agregação correta, o modelo aprenderia sobre contratos administrativos alheios (locações, eventos, energia) e violaria a Constituição do projeto (Art. I, II e III).

**Independent Test**: Pode ser testado executando a rotina de extração e verificando que a cardinalidade resultante é exatamente de 28.288 observações de 2025, que nenhum dos 36 hashes da quarentena contribuiu para o vetor agregado das obras afetadas, e que nenhuma medida financeira foi multiplicada pela ponte documental N:N.

**Acceptance Scenarios**:
1. **Given** a tabela `tcc.fato_risco` e suas dimensões com 28.288 observações de 2025, **When** a rotina de extração for executada, **Then** exatamente 28.288 registros devem ser gerados no dataset de 2025, com identificador único, atributos tabulares e representação vetorial (768 dimensões para obras com documentos válidos e vetor neutro/nulo com flag `has_embedding=False` para obras sem documentos).
2. **Given** os 36 documentos DNIT listados na quarentena oficial da Feature 012 (`quarentena_vinculos.json`), **When** os embeddings por obra forem agregados a partir dos chunks de `tcc.dim_embedding`, **Then** nenhum fragmento desses 36 documentos deve ser incluído na agregação das 22 obras DNIT correspondentes.
3. **Given** medidas financeiras monetárias (ex.: valor de investimento/contrato), **When** a agregação com a tabela ponte for calculada, **Then** o valor financeiro da obra deve permanecer idêntico ao da dimensão original, sem qualquer soma cumulativa decorrente da multiplicidade de documentos vinculados.

---

### User Story 2 - Particionamento estratificado por identidade de obra sem vazamento (Priority: P1)

Como pesquisador do projeto, desejo particionar a população rotulada de 2025 em subconjuntos de desenvolvimento/treino (80%) e teste/avaliação reservada (20%) agrupados estritamente por identidade da obra (`id_tcu`), de forma estratificada pelas 4 classes causais (0, 1, 2, 3), para que a avaliação dos modelos reflita a capacidade real de generalização para obras nunca vistas, sem vazamento de dados.

**Why this priority**: Conforme o Artigo I da Constituição e as boas práticas de MLOps, a mesma obra com múltiplos contratos, aditivos ou registros em bases diferentes não pode constar simultaneamente no conjunto de treino e no conjunto de teste. A partição agrupada e estratificada é pré-requisito indispensável antes de qualquer treino.

**Independent Test**: Pode ser testado gerando as partições com semente determinística (42) e checando se a interseção dos conjuntos de `id_tcu` entre desenvolvimento e teste é rigorosamente vazia (`set(dev_ids) & set(test_ids) == set()`), preservando ao mesmo tempo proporções semelhantes das classes 0, 1, 2 e 3 em ambos os conjuntos.

**Acceptance Scenarios**:
1. **Given** as 18.154 observações rotuladas de 2025 (16.649 classe 0; 978 classe 1; 104 classe 2; 423 classe 3), **When** o particionamento estratificado por grupos de `id_tcu` for aplicado, **Then** as partições devem conter aproximadamente 80% das obras no desenvolvimento (~14.523) e 20% no teste (~3.631), mantendo todas as 4 classes representadas em ambas as partições.
2. **Given** as listas de identificadores das obras atribuídas ao conjunto de desenvolvimento e ao conjunto de teste, **When** for calculada a interseção entre os identificadores únicos de obra (`id_tcu`), **Then** a interseção deve ser exatamente de zero elementos.

---

### User Story 3 - Isolamento de 2026, reserva de casos pendentes e manifesto de integridade (Priority: P2)

Como auditor do projeto, desejo que todas as 32.292 observações administrativas de 2026 e as 10.134 observações pendentes de 2025 (com `label_risco` NULL) sejam segregadas em partições específicas de inferência/aplicação futura, gerando um manifesto auditável com hashes SHA-256 e estatísticas descritivas, para assegurar rastreabilidade e impedir contaminação do alvo preditivo.

**Why this priority**: A Constituição (Art. I) veda terminantemente o uso de informações administrativas de 2026 como alvo ou treino histórico até 2025. Da mesma forma, as obras paralisadas cuja causa não possui evidência documental probatória não podem receber classes forçadas nem vazar no treino causal.

**Independent Test**: Pode ser testado verificando se os artefatos de dados exportados possuem partições claramente identificadas (`treino_dev`, `teste_retido`, `pendentes_2025`, `isolado_2026`), com hashes SHA-256 registrados em manifesto JSON auditável.

**Acceptance Scenarios**:
1. **Given** as 32.292 observações de 2026 no banco, **When** o pipeline de geração de datasets for concluído, **Then** 100% dessas observações devem estar na partição de isolamento de 2026, com zero ocorrências nos conjuntos de treino e teste.
2. **Given** as 10.134 observações de 2025 sem rótulo causal homologado, **When** o dataset for montado, **Then** todas devem ser alocadas na partição de casos pendentes, preservando `label_risco = NULL`.
3. **Given** os arquivos gerados no pipeline, **When** a gravação for finalizada, **Then** um arquivo de manifesto JSON deve ser gravado com SHA-256, contagens por partição, distribuição de classes e metadados de execução.

---

### Edge Cases

- **Obras sem documentos**: Devem ser preservadas na extração e na modelagem tabular; seu vetor de embedding deve ser representado por zeros ou marcado com `has_embedding = False`, evitando descartar obras válidas.
- **Obras cujos únicos documentos estão na quarentena**: Devem ser tratadas analogamente a obras sem documentos textuais, com flag `has_embedding = False` e anotação de quarentena.
- **Desbalanceamento severo da classe 2 (104 casos)**: O agrupamento por obra não pode deixar o conjunto de teste desprovido de instâncias da classe minoritária. O particionamento estratificado por grupos deve garantir presença da classe 2 no conjunto reservado.
- **Reprodutibilidade estrita**: A execução repetida da rotina com os mesmos parâmetros deve produzir exatamente os mesmos arquivos e mesmos hashes SHA-256.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE extrair as 28.288 observações de 2025 diretamente das tabelas `tcc.fato_risco` e `tcc.dim_obra`, mantendo correspondência exata 1:1 de observações sem perda de registros.
- **FR-002**: O sistema DEVE carregar o catálogo de quarentena documental gerado na Feature 012 (`quarentena_vinculos.json` ou equivalente) e excluir formalmente os 36 documentos incompatíveis da etapa de agregação textual.
- **FR-003**: O sistema DEVE calcular a agregação de embeddings (mean pooling dos vetores 768d normalizados dos fragmentos válidos de cada obra), gerando uma representação vetorial única por observação de obra e uma flag booleana `has_embedding`.
- **FR-004**: O sistema DEVE preservar as medidas financeiras e cadastrais no nível da obra, sem somar valores decorrentes da multiplicidade de documentos ou fragmentos associados na tabela ponte (Constituição Art. III).
- **FR-005**: O sistema DEVE implementar o particionamento estratificado por grupos de `id_tcu` (`StratifiedGroupKFold` ou partição de grupo balanceada com proporção 80/20) para as 18.154 observações rotuladas de 2025, com semente aleatória fixa (42).
- **FR-006**: O sistema DEVE validar e garantir que a interseção entre o conjunto de `id_tcu` de desenvolvimento e o conjunto de `id_tcu` de teste reservado seja estritamente vazia (`len(set_dev & set_test) == 0`).
- **FR-007**: O sistema DEVE isolar as 32.292 observações de 2026 e as 10.134 observações de 2025 pendentes em partições separadas de aplicação/inferência futura, garantindo que nenhuma delas participe do conjunto de treino ou teste rotulado.
- **FR-008**: O sistema DEVE salvar os datasets em formato de persistência eficiente e auditável (ex.: Parquet ou JSONL comprimido) e gerar um manifesto de integridade com hashes SHA-256, contagens por partição, distribuição por classe/base e data de extração.

### Key Entities

- **Dataset Observacional**: Tabela consolidada contendo atributos cadastrais, financeiros, situação original, rótulo homologado (`label_risco`), vetor de embedding médio (768 dimensões) e metadados de proveniência por obra/data-base.
- **Partição de Desenvolvimento (Treino/Validação)**: Subconjunto contendo ~80% das obras rotuladas de 2025, destinado exclusivamente para ajuste e validação cruzada interna dos classificadores.
- **Partição de Teste Reservada (Gold)**: Subconjunto intocado contendo ~20% das obras rotuladas de 2025, agrupado por identidade, reservado para a avaliação final e comparação dos modelos.
- **Manifesto de Integridade**: Registro em JSON com a impressão digital (SHA-256), data-base, quantidade de obras, distribuição de classes e garantia de conformidade com a Constituição.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das 28.288 observações de 2025 e das 32.292 observações de 2026 categorizadas nas partições corretas, sem descarte silencioso nem duplicação de linhas.
- **SC-002**: Interseção de obras entre partição de desenvolvimento e partição de teste rigorosamente igual a zero (`0% de vazamento de identidade`).
- **SC-003**: 0 fragmentos dos 36 documentos sob quarentena incorporados aos embeddings das obras.
- **SC-004**: Execução completa do pipeline de extração e particionamento em menos de 120 segundos, gerando manifesto com hashes auditáveis e idempotência garantida.

## Assumptions

- A conexão com o PostgreSQL local via `src/docker_runtime.py` / `src/database/connection.py` está disponível e saudável conforme verificado na Feature 013.
- Os 185.789 embeddings de dimensão 768 estão presentes na tabela `tcc.dim_embedding` sem vetores nulos para documentos processados na Sprint 4.
- A biblioteca `scikit-learn` ou equivalente para particionamento estratificado por grupos está disponível no ambiente virtual `.venv` ou pode ser importada deterministamente.
- O formato de persistência escolhido é acessível por bibliotecas padrão de ciência de dados (Pandas/NumPy) sem dependências externas adicionais.
