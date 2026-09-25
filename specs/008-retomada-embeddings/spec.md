# Feature Specification: Pendências documentais e retomada dos embeddings

**Feature Branch**: `codex/prontidao-carga`
**Created**: 2026-09-20
**Status**: Implemented and validated (bounded scope)
**Input**: Avançar nas pendências da Sprint 3 e implementar a Sprint 4 com Spec Kit.

## User Scenarios & Testing

### User Story 1 - Evidência das pendências (Priority: P1)

Como pesquisador, quero distinguir problemas ainda presentes de problemas resolvidos
nas fontes e identificar a evidência disponível de origem dos documentos.

**Why this priority**: Impede promover dados sem comprovação e torna a revisão executável.
**Independent Test**: Auditar um documento com arquivo alterado e comprovar sua rejeição.
**Acceptance Scenarios**:
1. Dadas as 27 quarentenas registradas, reavaliá-las nas fontes atuais e registrar
   motivo, evidência disponível e condição para resolução, sem inventar vínculos.
2. Dado um documento do piloto, conferir sua cadeia de coleta/extração/limpeza e
   arquivos físicos; ausência ou divergência impede declarar origem confirmada.

### User Story 2 - Processamento limitado e retomável (Priority: P1)

Como operador, quero executar embeddings em pequenos lotes e retomar o mesmo conjunto
após uma falha sem recalcular vetores já persistidos ou perder itens.

**Why this priority**: Permite ampliar ensaios controlados com rastreabilidade.
**Independent Test**: Interromper entre commit e relatório, retomar e observar zero duplicações.
**Acceptance Scenarios**:
1. Dado um conjunto congelado, processar os pendentes e reutilizar os compatíveis.
2. Dado um lote com um item inválido, nenhuma escrita desse lote permanece.
3. Dado conteúdo ou configuração alterados, bloquear retomada em vez de sobrescrever.

### Edge Cases

Arquivo ausente, URL sem comprovação, coleta rejeitada, modelo incompatível, manifestação
de sucesso sem commit, relatório atrasado após commit, dois operadores concorrentes,
texto acima da janela, IDs duplicados, lote vazio e hash/configuração divergentes.

## Requirements

### Functional Requirements

- **FR-001**: Reavaliar as 27 quarentenas e preservar exclusões quando faltar evidência.
- **FR-002**: Exportar evidência de origem do piloto sem inferir originalidade de nome, tipo ou URL.
- **FR-003**: Congelar seleção e configuração da execução para retomar exatamente o mesmo conjunto.
- **FR-004**: Persistir todos os itens de um lote atomicamente e registrar sucesso após confirmação.
- **FR-005**: Reutilizar vetores compatíveis antes da inferência; rejeitar incompatibilidade e alteração de fonte.
- **FR-006**: Manter textos, vínculos, fatos e rótulos intactos; respeitar separação dos anos.
- **FR-007**: Executar somente ensaios limitados nesta etapa; registrar evidências e testes de falha/retomada.

### Key Entities

- Dossiê de origem: identificação documental, cadeia de evidências, verificações físicas e pendências.
- Execução: seleção imutável, parâmetros de geração, lotes confirmados, falha e retomada.
- Conteúdo: fragmento canônico e seu vetor com proveniência; texto e tokenização imutáveis.

## Success Criteria

- **SC-001**: Todas as 27 quarentenas possuem disposição atual e nenhum vínculo foi inventado.
- **SC-002**: 100% dos documentos ligados ao piloto auditado possuem evidências ou falhas explícitas.
- **SC-003**: Retomada do mesmo conjunto não aumenta a contagem de vetores já concluídos nem os recalcula.
- **SC-004**: Falha em lote deixa zero itens desse lote parcialmente persistidos.
- **SC-005**: Regressão aprovada e contagens documentais/relacionais preservadas após ensaio operacional.

## Assumptions

- Os recursos locais e corpus existente podem ser inspecionados; preservar arquivos e alterações locais.
- Os ensaios podem gerar novos vetores em conjunto explicitamente limitado a até 512 conteúdos.
- Homologação humana de relevância e carga integral permanecem pendências da feature 007;
  esta etapa entrega infraestrutura e evidências, não declara esses critérios satisfeitos.
