# Implementation Plan: Pendências documentais e retomada

**Branch**: `codex/prontidao-carga` | **Date**: 2026-09-20 | **Spec**: [spec.md](spec.md)

## Summary
Auditar pendências da Sprint 3 e proveniência do piloto em leitura; implementar execução
limitada de embeddings com seleção congelada e retomada baseada no banco, não no status
potencialmente atrasado do relatório. Preservar a feature 007 e seus gates científicos.

## Technical Context
Python 3.14/Windows; PostgreSQL 17/pgvector; psycopg autocommit, JSON local atômico;
GTE/revisões/dependências da feature 007. Testes pytest com PostgreSQL descartável.
CLI de lote: até 512 conteúdos por execução, batch padrão 8 (inferência interna 2).
Reutilização deve evitar carregar o modelo quando todos os itens já estão concluídos.
Dossiê: todos os documentos vinculados aos vetores atuais, hashes e cadeia de metadados.

## Constitution Check
I: nenhuma alteração de rótulos ou promoção de 2026 a histórico.
II: arquivos e chunks intactos; toda divergência bloqueia reutilização.
III: cinco tabelas preservadas, sem DDL novo; digest dos tokens/configuração revalidado.
IV: transação externa por lote, parâmetros fixados, logs atômicos, testes antes de escrita.
Gates aprovados antes e depois do desenho. Não autoriza carga integral ou homologação humana.

## Project Structure
- `src/database/embedding_run.py`: seleção, manifesto, verificações e execução por lote.
- `src/database/embeddings.py`: persistência existente reforçada e escrita atômica por lote.
- `scripts/gerar_embeddings_sprint4.py`: CLI novo/retomar, dry-run padrão, limite obrigatório.
- `scripts/auditar_proveniencia_sprint3.py`: evidências físicas e cadeia do piloto.
- `tests/test_embedding_run.py`, `tests/test_proveniencia.py`, `tests/test_database_integration.py`.
- `logs/`: relatórios privados de execução e reauditoria das 27 quarentenas.

## Complexity Tracking
Sem migração de esquema. Lock de sessão por hash do conjunto impede dois operadores do
mesmo conjunto; bloqueio de linha em ordem de ID protege execuções com sobreposição.
Retomada consulta vetor/modelo/revisão e valida conteúdo; relatório sozinho nunca prova commit.
