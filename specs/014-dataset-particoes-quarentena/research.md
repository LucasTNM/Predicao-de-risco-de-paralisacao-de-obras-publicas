# Research & Technical Decisions: 014-dataset-particoes-quarentena

**Date**: 2026-10-01
**Feature**: [spec.md](spec.md)

## Decision 1: Agregação de Embeddings por Obra e Tratamento de Obras sem Documentos

- **Decision**: Aplicar mean pooling com normalização L2 sobre os vetores de 768 dimensões de todos os fragmentos pertencentes aos documentos válidos da obra. Para obras sem documentos válidos (ou cujos documentos foram integralmente quarentenados), atribuir vetor nulo ($\mathbf{0} \in \mathbb{R}^{768}$) acompanhado de uma flag booleana `has_embedding = False` e contador `num_documentos_validos = 0`.
- **Rationale**: 
  - A Constituição (Art. III) proíbe duplicar linhas ou somar valores pela ponte N:N. A agregação mean pooling condensa a representação semântica de múltiplos fragmentos em um único vetor denso de 768 dimensões por observação de obra.
  - A inclusão da flag `has_embedding` é fundamental para os modelos tabulares e híbridos (Random Forest), permitindo distinguir a ausência factual de documentos de uma representação próxima da origem.
- **Alternatives considered**:
  - *Max pooling*: Menos representativo do conteúdo documental global, suscetível a ruídos em fragmentos atípicos.
  - *Apenas o primeiro chunk*: Descarta partes essenciais de relatórios longos onde a causa de paralisação comumente aparece nos trechos finais.
  - *Descartar obras sem documentos*: Viola o Princípio I e III, pois o contraste de regularidade e a realidade administrativa contêm milhares de obras regulares sem acervo documental no banco.

## Decision 2: Aplicação da Quarentena Documental (Feature 012)

- **Decision**: Carregar os 36 hashes SHA-256 e identificadores de documentos catalogados na Feature 012 (`quarentena_vinculos.json`) e filtrá-los estritamente na consulta SQL/agregação de embeddings.
- **Rationale**: A auditoria documental dos 22 casos legados do DNIT comprovou desvio de objeto (locação de veículos, energia, coffee break, eventos). Excluí-los da agregação impede que ruídos contratuais contaminem o vetor semântico das obras afetadas.
- **Alternatives considered**:
  - *Excluir as obras do dataset*: Incorreto, pois a obra existe na `dim_obra` e na `fato_risco`; o que foi invalidado foi o vínculo dos documentos alheios.
  - *Apagar os documentos da base de dados*: Incorreto; a Constituição e as regras do projeto exigem preservação do banco e auditoria somente leitura, aplicando quarentena lógica nos extratores.

## Decision 3: Particionamento Estratificado por Grupos de Obra (`id_tcu`)

- **Decision**: Empregar divisão estratificada por grupos com semente reproduzível (random_state=42), agrupando por `id_tcu` e estratificando pelas 4 classes causais (0, 1, 2, 3), fixando divisão 80% treino/desenvolvimento e 20% teste reservado.
- **Rationale**: 
  - A Constituição (Art. I) e as diretrizes do Scikit-Learn estabelecem que a mesma obra física não pode ter registros divididos entre treino e teste (risco severo de vazamento por correlação temporal ou cadastral).
  - A classe 2 (deficiência orçamentário-financeira) conta com apenas 104 instâncias em 2025. O particionamento estratificado por grupos garante que essa classe minoritária mantenha proporção representativa (~20-21 casos) no conjunto de teste reservado.
- **Alternatives considered**:
  - *Train_test_split simples*: Causaria vazamento de dados de obras com múltiplos registros.
  - *Divisão temporal*: Para o corte histórico de 2025, todas as observações são da mesma data-base cadastral de 2025 (portanto, a separação por grupos de obras é o método correto e seguro).

## Decision 4: Estrutura e Formato dos Arquivos Exportados

- **Decision**: Armazenar os subconjuntos de dados particionados em arquivos Parquet com metadados embutidos e exportar um manifesto JSON com resumo estatístico e hashes SHA-256 em `dados_processados/sprint6/`.
- **Rationale**: Parquet mantém os tipos de dados originais (inclusive colunas vetoriais em arrays ou listas), possui leitura ultra-rápida, compressão compacta e facilita a computação do hash de integridade determinístico.
- **Alternatives considered**:
  - *CSV único*: Ineficiente para vetores densos de 768 dimensões (geraria arquivos gigantescos e perda de precisão de ponto flutuante).
  - *Pickle*: Inseguro para auditoria externa e dependente de versão específica de bibliotecas.
