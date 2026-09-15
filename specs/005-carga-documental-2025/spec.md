# Feature Specification: Carga Documental 2025 e Auditoria 2026

**Feature Branch**: `codex/carga-documental-2025`  
**Created**: 2026-09-15  
**Status**: Aprovado para Execução  
**Input**: Carga oficial e auditada dos 15.408 documentos elegíveis do ano de 2025 e preflight assíncrono de 2026.

---

## User Scenarios & Testing

### User Story 1 — Ingestão Transacional e Idempotente de 2025 (Priority: P1)
Como pesquisador do TCC, quero carregar os 15.408 documentos de 2025 auditados no banco PostgreSQL, gerando fragmentos sliding window determinísticos e vínculos na tabela ponte, para disponibilizar os dados textuais para o pipeline de NLP sem duplicar registros ou perder integridade.

**Independent Test**: Executar a carga em modo real com `--ano 2025 --dry-run False --excluir-quarentena`, verificar que todos os 15.408 documentos elegíveis entram em `dim_documento`, seus chunks em `dim_embedding` e seus vínculos em `ponte_documento_embedding`.

**Acceptance Scenarios**:
1. Given fontes de 2025 auditadas como `APTO`, When executar a carga, Then registrar 15.408 documentos em `dim_documento`.
2. Given fragmentos de texto gerados pelo chunker (450 tokens / 50 overlap), When existirem chunks idênticos, Then deduplicar canonicamente em `dim_embedding` e registrar ocorrências distintas na tabela ponte.
3. Given execução em produção, When gravar no banco, Then as colunas `embedding` e `label_risco` DEVEM permanecer estritamente `NULL`.
4. Given reexecução, When rodar novamente, Then o pipeline deve ser idempotente (não duplicar documentos ou chunks).

### User Story 2 — Auditoria e Validação Pós-Carga (Priority: P1)
Como pesquisador, quero verificar automaticamente a integridade relacional do banco após a carga, para assegurar ausência de inconsistências ou quebras de chave estrangeira.

**Independent Test**: Executar `validate_data(conn)` e garantir zero inconsistências em todas as 9 métricas relacionais.

**Acceptance Scenarios**:
1. Given banco populado com 2025, When rodar `validate_data(conn)`, Then o retorno deve ser `valido: True` com 0 inconsistências.
2. Given verificação de catálogo, When inspecionar tabelas, Then todas as constraints e assinaturas DDL devem permanecer válidas.

### User Story 3 — Preflight Físico de 2026 em Background (Priority: P2)
Como pesquisador, quero concluir a leitura física e cálculo de hashes dos 35.602 arquivos de 2026 em modo `dry-run`, para certificar a base para etapas futuras sem afetar o banco.

**Acceptance Scenarios**:
1. Given preflight de 2026, When executar em segundo plano, Then inspecionar todos os arquivos físicos e gerar relatório de prontidão sem tocar no banco de dados.

---

## Requirements

### Functional Requirements
- **FR-001**: O sistema DEVE carregar apenas os documentos de 2025 aprovados no preflight, excluindo quarentenas.
- **FR-002**: Cada documento e seus chunks associados DEVEM ser persistidos numa transação atômica.
- **FR-003**: Os vetores de embedding (`dim_embedding.embedding`) DEVEM permanecer `NULL` (escopo da Sprint 4).
- **FR-004**: A validação pós-carga DEVE verificar ausência de orfãos entre fatos, documentos e embeddings.
- **FR-005**: O preflight de 2026 DEVE rodar em modo `dry_run=True` sem abrir conexão de escrita com o banco.

### Success Criteria
- **SC-001**: Ingestão bem-sucedida de 15.408 documentos de 2025.
- **SC-002**: `validate_data(conn)` reporta 0 inconsistências e `valido: True`.
- **SC-003**: Nenhuma mutação não autorizada em 2026 no banco operacional.
- **SC-004**: Todos os 56 testes de regressão permanecem verdes.
