# Feature Specification: 019-motor-rag-evidencias

**Feature Branch**: `019-motor-rag-evidencias`

**Created**: 2026-10-19

**Status**: Draft (depende do relatório da Feature 018)

**Input**: Card Trello "Desenvolvimento do Motor de Busca RAG" — programar a busca por similaridade do cosseno no pgvector para recuperar os fragmentos textuais mais relevantes antes da classificação final do modelo.

## Ponto de partida

A Sprint 4 entregou busca cosseno exata **global** (`src/database/vector_search.py`,
mediana 177,5 ms, filtros por ano/origem, proveniência). Ainda não existe a
recuperação **por obra** que seleciona os k fragmentos de evidência que alimentam o
classificador, nem o filtro das fontes vetadas pela Feature 018.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seleção de evidências por obra (Priority: P1)

Como pesquisador, quero recuperar, para cada obra, os k fragmentos mais similares a
um conjunto fixo de consultas causais (técnica, orçamentário-financeira,
abandono/contratada e regularidade), restritos aos documentos da própria obra e às
fontes permitidas, para montar a entrada textual do classificador.

**Why this priority**: É o insumo direto do BERTimbau (Feature 020/021); sem ele o modelo leria fragmentos arbitrários ou excederia o limite de 512 tokens.

**Independent Test**: Para uma amostra de obras do treino, a saída lista k fragmentos com distância, documento, offsets e consulta de origem; nenhum fragmento pertence a outra obra ou a fonte vetada.

**Acceptance Scenarios**:

1. **Given** uma obra com documentos permitidos, **When** a recuperação for executada, **Then** retorna até k fragmentos ordenados por similaridade, com desempate determinístico.
2. **Given** uma obra sem documentos permitidos, **When** a recuperação for executada, **Then** retorna lista vazia e a marca `sem_evidencia_textual`, sem buscar fragmentos de outras obras.
3. **Given** um fragmento de ficha sintética vetado pela Feature 018, **When** a recuperação for executada, **Then** ele nunca aparece no resultado.

---

### User Story 2 - Consultas causais versionadas e sem vazamento (Priority: P1)

Como pesquisador, quero que as consultas causais sejam textos fixos, versionados e
que não contenham termos da situação da obra (ex.: "paralisada"), para que o
recuperador não reintroduza o alvo.

**Independent Test**: Arquivo de consultas com hash no manifesto; teste falha se uma consulta contiver termo da lista proibida.

**Acceptance Scenarios**:

1. **Given** o arquivo de consultas, **When** um termo proibido for incluído, **Then** a execução é recusada.

---

### User Story 3 - Lote de evidências congelado por partição (Priority: P2)

Como pesquisador, quero materializar as evidências recuperadas de `treino_dev` e
`teste_retido` em artefatos imutáveis com manifesto, para que treino e avaliação
leiam exatamente os mesmos fragmentos e o experimento seja reproduzível.

**Independent Test**: Duas execuções consecutivas geram o mesmo hash.

**Acceptance Scenarios**:

1. **Given** as partições da Feature 014, **When** o lote for gerado, **Then** cada obra aparece exatamente uma vez e a interseção de obras entre partições é zero.

### Edge Cases

- Chunks compartilhados por várias obras: permitidos apenas se vinculados à obra consultada; registrar a duplicidade.
- Obra com menos de k fragmentos: retornar os disponíveis, sem preenchimento artificial.
- Obras de 2026 e pendentes: fora do lote de treino/teste (Art. I).
- Classe 1 quase sem texto (966/978 sem documentos): o lote deve reportar a cobertura por classe.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A recuperação DEVE usar distância cosseno exata sobre os vetores GTE existentes, sem índice aproximado.
- **FR-002**: A busca DEVE ser restrita aos fragmentos vinculados à obra consultada pela ponte documental.
- **FR-003**: O sistema DEVE aplicar a lista de fontes permitidas/vetadas produzida pela Feature 018.
- **FR-004**: k e o conjunto de consultas DEVEM ser parâmetros versionados (padrão inicial: k = 4 por obra, deduplicados).
- **FR-005**: Cada fragmento retornado DEVE carregar proveniência (documento, offsets, distância, consulta).
- **FR-006**: O lote materializado DEVE registrar cobertura por classe e por partição e hash SHA-256.
- **FR-007**: O banco DEVE ser acessado somente em leitura.

### Key Entities

- **Consulta Causal**: texto fixo, classe causal associada, versão.
- **Evidência Recuperada**: obra, fragmento, distância, consulta de origem, posição no ranking.
- **Lote de Evidências**: conjunto congelado por partição com manifesto.

## Success Criteria *(mandatory)*

- **SC-001**: 100% dos fragmentos recuperados pertencem à obra consultada e a fontes permitidas.
- **SC-002**: Recuperação do lote completo (18.154 obras) em menos de 30 min.
- **SC-003**: Reexecução gera artefatos idênticos (hash igual).
- **SC-004**: Relatório de cobertura mostra, por classe, a fração de obras com pelo menos um fragmento.
- **SC-005**: Amostra de 30 obras inspecionada manualmente com relevância registrada (julgamento assistido, não rótulo).

## Assumptions

- Os vetores GTE da Sprint 4 continuam válidos; vetores de fichas mascaradas, se aprovados, vêm da Feature 018.
- Os chunks já estão tokenizados com BERTimbau cased (450 + 50), compatíveis com o limite de 512 tokens.
- "RAG" aqui significa recuperação de evidências para classificação; não há geração de texto por LLM.
