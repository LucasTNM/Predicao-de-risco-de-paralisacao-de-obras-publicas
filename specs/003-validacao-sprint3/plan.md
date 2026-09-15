# Implementation Plan: Validação e correções da Sprint 3

**Branch**: `main` (sem alteração do checkout) | **Date**: 2026-09-10 | **Spec**: [spec.md](spec.md)

**Input**: `specs/003-validacao-sprint3/spec.md`

## Summary

Adotar o Spec Kit 1.0.6 com integração agy e formalizar as nove ADRs antes das
correções. Reproduzir falhas de preflight, retomada, auditoria e persistência dos
relatórios; corrigir sem alterar o esquema de negócio nem o banco de carga.

## Technical Context

**Language/Version**: Python 3.14.3, PowerShell no Windows.
**Primary Dependencies**: Psycopg 3.3.5, transformers 4.57.6, tokenizers 0.22.2,
openpyxl 3.1.5 e specify-cli 1.0.6 instalado somente em `.venv`.
**Storage**: PostgreSQL 17 + pgvector 0.8.6; corpus anual no Drive, somente leitura.
**Testing**: Pytest 8.3.5 e banco `tcc_test_<uuid>` descartável.
**Target Platform**: Windows, PostgreSQL local; portabilidade LF/CRLF.
**Project Type**: CLI Python de ingestão e preparação de corpus.
**Performance Goals**: Manifestos lidos uma vez, índices em memória; arquivos
validados em streaming quando possível e tokenização limitada a um documento.
**Constraints**: Sem pesos do BERT, embeddings, rótulos inferidos, limpeza de dados
existentes ou migração automática; base isolada para mutações de teste.
**Scale/Scope**: Validar implementação e estado observável; os 51.234 textos e
60.580 snapshots são referências históricas até nova medição explicitada.

## Constitution Check

Gate antes e depois do desenho: aprovado.

- I: snapshots preservados; rótulos pendentes; sem experimento com dados futuros.
- II: UTF-8, hashes e recortes canônicos; rejeições com motivo.
- III: cinco tabelas e ponte preservadas; reuso deve comparar conteúdo e ocorrências.
- IV: versões fixas, relatórios atômicos, testes isolados e resultados reproduzíveis.

## Project Structure

### Documentation (this feature)

`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli.md`,
`quickstart.md`, `tasks.md`, `checklists/requirements.md`, `validation.md`.

### Source Code (repository root)

- `.specify/`, `.agents/skills/`: scaffolding oficial e constituição.
- `src/database/preflight.py`, `load_documentos.py`: validação física compartilhada
  e retomada por comparação das ocorrências esperadas.
- `src/database/schema.py`, `validation.py`: assinatura estável e verificações de
  integridade complementares, sem reescrever o DDL de banco já homologado.
- `src/database/run_load.py`: relatório local atômico e erro de persistência visível.
- `scripts/testar_sprint3.py`: usar Pytest também na integração e manter isolamento.
- `tests/test_database_*.py`, `tests/test_higienizacao.py`: cenários de regressão,
  sem acesso acidental a Gemini e sem depender da chave do `.env`.

**Structure Decision**: Manter o projeto único e os módulos existentes; adicionar
helper somente se necessário para evitar duas validações físicas divergentes.

## Implementation Strategy

1. Encerrar pesquisa e registrar evidências e baseline (29 passed, 6 skipped).
2. Testes devem demonstrar cada defeito antes da implementação.
3. Conferir PDF/TXT, metadados numéricos e qualidade no preflight; registrar hashes
   calculados para detectar troca do TXT após auditoria. Revalidar na carga.
4. Comparar ponte, conteúdo e tokenização antes de reutilizar documento; falha
   exige `--force`. Validar chave de conteúdo e continuidade na auditoria do banco.
5. Tornar assinatura independente de search_path e quebra de linha. Nenhuma
   adoção automática de schema incompatível; manter recusa com orientação explícita.
6. Persistir relatório por arquivo temporário e replace, sem engolir falhas de I/O.
7. Rodar suíte e integração real; consultar banco existente em modo somente leitura
   e, quando disponível, preflight real. Documentar limites em validation.md.
8. Executar speckit-converge após a implementação; anexar tarefas se houver lacunas.

Refinamento durante a validação física: leituras seriais do Drive têm latência
significativa. Usar cinco workers e no máximo dez documentos pendentes por lote,
mantendo ordem determinística e resultado por documento. Relatar progresso a cada
mil documentos verificados; nenhum worker modifica fontes ou acessa o banco.

## Complexity Tracking

Nenhuma violação dos artigos; não introduzir novos serviços, filas ou tabelas.
