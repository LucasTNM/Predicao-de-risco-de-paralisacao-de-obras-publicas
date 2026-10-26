# Implementation Plan: 018-auditoria-vazamento-rebaseline

**Branch**: `018-auditoria-vazamento-rebaseline` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/018-auditoria-vazamento-rebaseline/spec.md`

## Summary

Feature de bloqueio (*gate*) da Sprint 7. Ela formaliza a auditoria de vazamento
(fichas sintéticas que expõem a situação "Paralisada" e proxies de presença
documental), reexecuta os modelos de referência da Sprint 6 nos cenários C0–C3,
elege uma referência oficial sem vazamento e define as fontes textuais permitidas
para o RAG (019) e o BERTimbau (020/021).

## Technical Context

**Language/Version**: Python 3.14 (`.venv` para modelagem; `.venv-sprint4-gpu` para recalcular vetores GTE).

**Primary Dependencies**: `lightgbm`, `scikit-learn`, `duckdb`, `pandas`, `numpy`, `psycopg`, `sentence-transformers` (GTE fixado na Sprint 4).

**Storage**: PostgreSQL/pgvector (somente leitura); artefatos derivados em `dados_processados/sprint7/` (ignorado pelo Git) com manifesto SHA-256.

**Testing**: `pytest` (unitários de mascaramento e de seleção de atributos; integração com o banco descartável do runner).

**Target Platform**: Windows 11 local, RTX 5060.

**Project Type**: pipeline CLI de ciência de dados.

**Performance Goals**: rebaseline completo (4 modelos × 4 cenários × 5 dobras) em menos de 30 min; recálculo de ~14,7 mil vetores mascarados em menos de 15 min na GPU.

**Constraints**: nenhuma escrita em `tcc.*`; teste retido consultado uma única vez; partições da Feature 014 imutáveis.

**Scale/Scope**: 18.154 observações rotuladas; 14.709 chunks de fichas de 2025.

## Constitution Check

| Princípio | Exigência | Situação no desenho |
| :--- | :--- | :---: |
| I. Fidedignidade e rótulo real | Fichas sintéticas distinguidas para evitar vazamento do alvo | **Motivação da feature**: corrige a violação identificada |
| II. Integridade semântica | Mascaramento não pode inventar nem resumir conteúdo | PASS: remoção apenas de campos catalogados, com offsets registrados |
| III. Consistência relacional | 1 observação por obra; sem somas pela ponte N:N | PASS: agregação por `id_fato` reaproveita a lógica da Feature 014 |
| IV. Reprodutibilidade | Semente 42, manifesto e testes antes de commit | PASS: manifesto por cenário; pytest obrigatório |

## Project Structure

### Documentation (this feature)

```text
specs/018-auditoria-vazamento-rebaseline/
├── spec.md
├── plan.md
├── tasks.md
├── checklists/requirements.md
├── catalogo_vazamento.md      # a gerar (T003)
└── report.md                  # a gerar (T010)
```

### Source Code (previsto)

```text
src/dataset/
├── leakage_audit.py           # consultas somente leitura e termos reveladores
└── masking.py                 # mascaramento determinístico de campos das fichas
src/modeling/loader.py         # perfis de atributos por cenário; imputação ajustada no treino
scripts/
├── auditar_vazamento_sprint7.py
└── rebaseline_sprint7.py
tests/
├── test_leakage_audit.py
└── test_masking.py
```

**Structure Decision**: reaproveitar `src/dataset` e `src/modeling`; nenhum novo pacote.

## Decisões e riscos

- **Mascaramento vs. exclusão**: C2 (exclusão) é o cenário conservador; C3 (mascaramento) só é elegível se SC-004 for comprovado.
- **Reuso do teste retido**: documentado como segunda e última consulta, com cenário pré-registrado no `report.md` antes da execução.
- **Classe 1 sem texto**: espera-se que modelos textuais não a aprendam; a referência tabular continua responsável por ela.
