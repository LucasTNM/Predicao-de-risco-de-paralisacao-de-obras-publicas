# Feature Specification: Sprint 5 — rotulagem histórica de risco

**Feature Branch**: `codex/sprint5-rotulagem`
**Created**: 2026-09-28
**Status**: Validada; execução autorizada pelo pesquisador
**Input**: Planejar a sprint inteira e iniciar rotulagem 0–3 conforme PCC, usando Spec Kit e Docker existente.

## User Scenarios & Testing

### User Story 1 — Aplicar taxonomia rastreável (Priority: P1)
Como pesquisador, quero converter causas inequívocas de 2025 em rótulos reproduzíveis e identificar exceções.
**Why this priority**: Pré-requisito do dataset supervisionado.
**Independent Test**: Casos controlados e simulação integral reproduzem catálogo sem alterar o banco.
**Acceptance Scenarios**:
1. Causa exata inequívoca de 2025 com situação paralisada produz classe 1, 2 ou 3 com causa original, regra, versão e fonte.
2. Causa ausente, genérica, multicausal ou contraditória preserva NULL com motivo de pendência.
3. Observação de 2026 fica fora do alvo histórico, sem copiar rótulos entre anos.

### User Story 2 — Revisar evidências das quatro classes (Priority: P1)
Como pesquisador, quero fila de revisão e importar decisões explícitas com autoria e evidência histórica verificável.
**Why this priority**: Classe 0 e ambiguidades não podem ser inferidas por ausência de dados.
**Independent Test**: Decisões 0–3 válidas são aceitas; fonte ausente, futura, sintética ou modificada é rejeitada.
**Acceptance Scenarios**:
1. Decisão 0 exige evidência original de andamento normal/conclusão sem apontamentos graves, revisor, justificativa, data e trecho verificável.
2. Conflitos exigem classe escolhida e justificativa, sem prioridade numérica automática.
3. Fonte ou snapshot alterado após exportação rejeita todo o lote sem escrita parcial.

### User Story 3 — Auditar e preparar continuidade (Priority: P2)
Como pesquisador, quero distribuição por classe/base, cobertura e pendências, preservando corpus e embeddings.
**Why this priority**: Avaliar prontidão real e evitar declarar treino pronto sem classe de contraste.
**Independent Test**: Reexecução não reescreve decisões e reload invalida rótulos cujo contexto mudou.
**Acceptance Scenarios**:
1. Repetir lote reutiliza decisões idênticas e rejeita sobrescritas divergentes.
2. Falha durante persistência reverte todo o lote.
3. Relatório distingue regra, revisão humana, pendência e exclusão temporal; não atribui homologação humana ao agente.

### Edge Cases
Zero é válido e distinto de NULL; booleano não é classe. Causa desconhecida não vira zero. Rescisão genérica, dificuldade financeira/técnica da executora e causas múltiplas requerem revisão. Concluída com abandono é conflito. Ficha sintética não valida o próprio alvo. Mudança apenas de situação/fonte também invalida rótulo.

## Requirements
### Functional Requirements
- **FR-001**: Definir classes conforme PCC §2.4.2 e §3.2 (páginas impressas 16 e 27; PDF 17 e 28) e ADR-001, com catálogo versionado de correspondência exata conservadora.
- **FR-002**: Rotular somente observações de 2025; preservar 2026 e entradas desconhecidas; rejeitar sobrescrita de rótulo divergente.
- **FR-003**: Exportar inventário de causas/situações e fila completa por fato com chave, fingerprint e motivo sem expansão N:N.
- **FR-004**: Importar revisão 0–3 com revisor, justificativa, fonte textual original local, SHA-256, data até a data-base e trecho literal. Classe 0 exige declaração explícita de regularidade sem apontamentos graves.
- **FR-005**: Persistir rótulo e proveniência juntos, com versão/hash das regras ou revisão, snapshot, método, data e autor do processamento; transação, simulação padrão e idempotência.
- **FR-006**: Invalidar rótulos quando carga alterar contexto; auditar proveniência sem reprovar automaticamente todo rótulo não nulo como na Sprint 3.
- **FR-007**: Auditar distribuição/preservação; testes unitários e PostgreSQL descartável cobrem falhas, retomada, datas e concorrência.
- **FR-008**: Atualizar plano, diário, próximos passos, guia e relatório Spec Kit com limitações e revisão humana remanescente.

### Key Entities
Observação (obra/data-base/causa/contexto); regra (código/classe/causa/justificativa); decisão (rótulo/método/motivo/fingerprint); revisão (revisor/fonte/data/trecho); execução (inventário/distribuição/alterações/integridade).

## Success Criteria
- **SC-001**: Todas as 60.580 observações atuais no inventário por ano; todas de 2025 com decisão ou motivo de pendência.
- **SC-002**: 100% dos rótulos aplicados com proveniência verificável; zero classe 0 padrão e zero atribuições a 2026.
- **SC-003**: Repetição válida produz zero atualizações; falha produz zero alterações no lote.
- **SC-004**: Conteúdo alheio ao rótulo preservado; testes afetados e integração real aprovados.
- **SC-005**: Guia permite revisar pendências e identificar o que falta para dataset homologado.

## Assumptions
- Sprint inteira: protocolo, automação conservadora, revisão e auditoria. Treinamento, splits e pesos ficam para etapa posterior.
- Entrega classifica causas históricas, sem alegar previsão antecipada; objetivo preditivo do PCC exige experimento futuro com corte de atributos.
- Pedido autoriza aplicar regras inequívocas, sem inventar aprovação humana. Homologação científica e ambiguidades dependem de revisão posterior.
- Cinco tabelas preservadas: proveniência estruturada serializada em origem_rotulo existente; sem migração nesta sprint.
