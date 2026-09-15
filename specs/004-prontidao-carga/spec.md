# Feature Specification: Prontidão antes da carga integral

**Feature Branch**: `codex/prontidao-carga`, preservando alterações locais anteriores
**Created**: 2026-09-15
**Status**: Especificado
**Input**: "Vamos seguir para o próximo passo e resolver as pendências antes de subir a carga."

## User Scenarios & Testing

### User Story 1 — Auditoria integral rastreável (Priority: P1)
Como pesquisador, quero conferir as fontes de 2025 e 2026 e acompanhar o progresso,
para conhecer os documentos elegíveis sem inserir dados no banco.
**Independent Test**: confrontar relatórios com inventário; simular interrupção.
**Acceptance Scenarios**:
1. Given fontes disponíveis, When auditar ambos os anos, Then cada texto tem
   destinação e só é elegível após conferência física.
2. Given auditoria longa, When interromper, Then preservar anos concluídos e
   progresso parcial explicitamente não homologado.
3. Given auditoria, When executar, Then não executar carga, vetores ou rotulagem.

### User Story 2 — Destinação das pendências (Priority: P1)
Como pesquisador, quero motivos e evidências para excluir ou manter em quarentena
fontes inadequadas, sem inventar vínculos, liberar rejeitados ou apagar arquivos.
**Independent Test**: conferir cada ocorrência por identidade, motivo e destinação.
**Acceptance Scenarios**:
1. Given rejeição anterior, When decidir a destinação, Then preservar a rejeição.
2. Given vínculo ausente/ambíguo ou baixa qualidade, When faltar evidência para
   correção, Then manter fora do lote e registrar a condição de reentrada.

### User Story 3 — Preparação reproduzível (Priority: P2)
Como pesquisador, quero documentação coerente e código verificável para executar
carga posteriormente sem confundir elegibilidade com aptidão para treinamento.
**Independent Test**: revisar roteiro, regressão e banco antes/depois.
**Acceptance Scenarios**:
1. Given carga documental e vetorização distintas, When seguir roteiro, Then
   preparar documentos/chunks antes dos embeddings.
2. Given evidências concluídas, When entregar, Then separar resultados atuais,
   limitações e pendências futuras; proteger dados e credenciais do versionamento.

### Edge Cases
- Interrupção antes do primeiro progresso, falha de relatório e perda do Drive.
- PDF/TXT ausente/alterado, UTF-8 inválido, vínculo múltiplo, coleta rejeitada.
- Fonte alterada durante auditoria; manifesto OK sem validação física.
- Fichas sintéticas e snapshots de 2026 usados indevidamente como evidência histórica.

## Requirements
### Functional Requirements
- **FR-001**: Auditar ambos os anos integralmente preservando fontes e banco.
- **FR-002**: Publicar progresso e resultados anuais resistentes a interrupção.
- **FR-003**: Registrar decisão, evidência e condição de reentrada de cada pendência.
  Impedir carga com quarentenas sem decisão explícita de mantê-las fora do lote.
- **FR-004**: Corrigir documentação sobre ordem de carga e vetorização.
- **FR-005**: Validar mudanças com regressão e integração isolada quando afetada;
  conferir banco operacional em leitura antes/depois.
- **FR-006**: Consolidar artefatos revisáveis/versionáveis sem corpus, credenciais
  ou logs operacionais e sem publicação remota.
### Key Entities
- Auditoria: escopo, início, progresso, inventário elegível, fontes e estado final.
- Ocorrência: ano/base/arquivo, motivo, evidência e destinação conservadora.
- Evidência de prontidão: testes, integridade do banco, limitações e roteiro.

## Success Criteria
- **SC-001**: 100% dos textos manifestados têm destinação; elegíveis verificados fisicamente.
- **SC-002**: Zero mutações no banco operacional e nas fontes.
- **SC-003**: Toda pendência tem destinação; nenhuma promovida sem evidência.
- **SC-004**: Testes afetados passam; relatório permite reproduzir verificações.

## Assumptions
- Auditoria pode demorar devido ao Drive; progresso parcial não aprova o corpus.
- Manter documento inseguro fora do lote resolve sua destinação operacional,
  sem declarar recuperados dados ausentes ou ambiguidades sem comprovação.
- Não há autorização de carga nesta etapa; preservar DDL, 450/50, rótulos e origem.
- Múltiplos snapshots intra-ano e treino são evolução futura; fontes atuais têm uma data por ano.
