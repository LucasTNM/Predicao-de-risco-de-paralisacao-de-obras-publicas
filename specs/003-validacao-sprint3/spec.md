# Feature Specification: Validação e correções da Sprint 3

**Feature Branch**: `main` (checkout existente; feature independente da branch)

**Created**: 2026-09-10

**Status**: Implementação/piloto validados; limites documentados em validation.md

**Input**: "Valide a implementação feita da sprint 3 e caso haja melhorias, faça.
Quero também que utilize o spec kit antes de fazer qualquer trabalho."

## User Scenarios & Testing

### User Story 1 - Governança reproduzível (Priority: P1)

Como pesquisador, quero as nove ADRs preservadas e um fluxo auditável antes de
alterar a Sprint 3, para relacionar cada correção a um requisito científico.

**Why this priority**: É a pré-condição explícita da revisão.

**Independent Test**: Verificar constituição, skills, especificação, plano e tarefas.

**Acceptance Scenarios**:

1. **Given** um checkout com alterações locais, **When** inicializar a governança,
   **Then** preservar o trabalho existente e produzir arquivos versionáveis.
2. **Given** as nove ADRs, **When** revisá-las, **Then** todas têm rastreabilidade
   na constituição, sem flexibilizar o limite histórico de 2025 para rótulos.

### User Story 2 - Carga documental íntegra (Priority: P1)

Como pesquisador, quero repetir ou retomar uma carga sem duplicação, perda de
texto ou mudança silenciosa de vínculo, preservando obra e data-base.

**Why this priority**: Falhas comprometem o corpus e os experimentos posteriores.

**Independent Test**: Usar documentos sintéticos com falhas, repetição e alterações
controladas, verificando conteúdo, relações e medidas antes/depois.

**Acceptance Scenarios**:

1. **Given** documento elegível, **When** fragmentá-lo, **Then** cobrir todos os
   tokens com offsets exatos, limites válidos e sobreposição configurada.
2. **Given** carga concluída, **When** repeti-la, **Then** manter conteúdo e contagens.
3. **Given** arquivo, configuração ou vínculos alterados, **When** carregar,
   **Then** exigir substituição explícita e atômica sem resíduos incorretos.
4. **Given** manifestos rejeitados, ambíguos ou inconsistentes, **When** auditar,
   **Then** registrar a destinação sem promover documentos indevidos.

### User Story 3 - Evidência verificável de prontidão (Priority: P2)

Como autor do TCC, quero um relatório com resultados reproduzidos e limites reais,
para não confundir piloto aprovado com carga integral homologada.

**Why this priority**: Evita conclusões acadêmicas acima da evidência disponível.

**Independent Test**: Executar regressão e integração isolada, confrontar os
resultados com o relatório e listar pendências operacionais separadamente.

**Acceptance Scenarios**:

1. **Given** verificações concluídas, **When** relatar, **Then** informar contagens,
   falhas, skips e limitações sem apresentar resultados históricos como atuais.

### Edge Cases

- Texto vazio, subtokens nas bordas, limite exato, cauda e parâmetros inválidos.
- Documento compartilhado, troca de vínculo com mesma contagem e arquivo alterado
  após preflight; rollback e execução concorrente.
- Metadados ausentes, qualidade não finita, duplicatas de snapshot, divergência
  estrutural, credenciais em mensagens de erro e banco indisponível.

## Requirements

### Functional Requirements

- **FR-001**: Instalar governança isolada, com versão fixa, skills válidas e nove ADRs.
- **FR-002**: Registrar especificação, plano e tarefas antes das correções.
- **FR-003**: Preservar snapshots, grão da fato, integridade N:N e valores exatos.
- **FR-004**: Preservar texto/tokens/offsets; rejeitar configuração inválida.
- **FR-005**: Reconciliar fontes e quarentenas com proveniência e leitura íntegra.
- **FR-006**: Validar reuso pelo conteúdo e vínculos, com rollback e reprocessamento
  explícito; detectar schema incompatível sem apagar dados.
- **FR-007**: Manter rótulos e vetores pendentes; não gerar embeddings nesta revisão.
- **FR-008**: Executar regressão e integração real isolada e documentar as correções.
- **FR-009**: Distinguir implementação/piloto da homologação integral do corpus.

### Key Entities

- **Observação**: obra identificada por base, identificador textual e data-base.
- **Documento**: fonte anual com hashes, caminhos, qualidade e proveniência.
- **Fragmento e ocorrência**: conteúdo reutilizável com tokens; vínculo e offsets
  específicos por documento e observação.
- **Evidência de validação**: requisito, cenário reproduzido, resultado e limite.

## Success Criteria

### Measurable Outcomes

- **SC-001**: As nove ADRs e todas as correções têm rastreabilidade escrita.
- **SC-002**: Zero regressões nos cenários executados e zero inconsistências na
  base isolada de integração após carga e reexecução.
- **SC-003**: Cada defeito corrigido tem um cenário que falha antes e passa depois.
- **SC-004**: Relatório explicita quais volumes foram efetivamente validados e
  quais dependem de homologação operacional posterior.

## Assumptions

- Esta revisão preserva alterações locais anteriores e usa base de teste isolada.
- Consulta ao corpus/banco existente é somente leitura; carga integral é etapa
  operacional distinta, não necessária para reproduzir defeitos da implementação.
- A primeira feature exercita o fluxo na Sprint 3. Sprint 4, fine-tuning e RAG
  não serão implementados por este pedido.
