# Implementation Plan: 014-dataset-particoes-quarentena

**Branch**: `014-dataset-particoes-quarentena` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-dataset-particoes-quarentena/spec.md`

## Summary

Esta feature implementa o pipeline de engenharia de dados preparatório para a modelagem supervisionada de risco de paralisação. Extrai as observações históricas do PostgreSQL, agrega vetores de embedding textuais (768 dimensões) por observação de obra aplicando a quarentena lógica aos 36 documentos DNIT não relacionados (Feature 012), e particiona a população rotulada de 2025 (18.154 obras) em treino/desenvolvimento (80%) e teste reservado (20%) agrupando estritamente por identidade da obra (`id_tcu`), garantindo ausência matemática de vazamento de dados. As observações de 2026 (32.292) e os casos pendentes de 2025 (10.134) são segregados em partições isoladas com manifesto JSON auditável.

## Technical Context

**Language/Version**: Python 3.14.3 (ambiente virtual `.venv`)
**Primary Dependencies**: `psycopg` (3.3.6), `pandas` (3.0.5), `numpy` (2.5.2), `pyarrow` ou `fastparquet` para Parquet, `scikit-learn` ou particionador determinístico customizado para `StratifiedGroupSplit`.
**Storage**: PostgreSQL local (banco transacional e dimensional `tcc_db`), arquivos Parquet e manifestos JSON locais em `dados_processados/sprint6/`.
**Testing**: `pytest` (8.3.5), testes unitários e de integração real com banco PostgreSQL.
**Target Platform**: Windows 11 x64 / Docker Desktop.
**Project Type**: Data pipeline / CLI script / Python module.
**Performance Goals**: Extração consolidada e particionamento das 60.580 observações concluídos em menos de 60 segundos.
**Constraints**: 
- Não alterar dados existentes no banco (operações de leitura estrita).
- Proibição absoluta de vazamento de `id_tcu` entre partição de desenvolvimento e partição de teste.
- Preservação integral dos princípios da Constituição (Artigos I, II, III e IV).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Exigência Constitucional | Status no Design |
| :--- | :--- | :---: |
| **I. Fidedignidade histórica e rótulo real** | Estados de 2026 NÃO entram no treino histórico até 2025; obras sem evidência mantêm NULL; partição deve contrastar classes e impedir vazamento da mesma obra. | **PASS**: 2026 é segregado em partição isolada; obras com NULL vão para partição pendente; agrupamento estrito por `id_tcu` impede vazamento. |
| **II. Integridade semântica dos documentos** | Quarentena lógica: documentos incompatíveis com o contrato devem ser excluídos com motivo formal registrado. | **PASS**: Os 36 documentos DNIT da Feature 012 são filtrados da agregação de embeddings com motivo registrado no manifesto. |
| **III. Consistência relacional e dimensional** | 1 observação por obra/data-base na fato_risco; medidas financeiras NÃO DEVEM ser somadas após expansão N:N da ponte; agregação vetorial determinística. | **PASS**: Extração 1:1 com fato_risco; agregação vetorial por mean pooling sem somar valores financeiros. |
| **IV. Reprodutibilidade de ML e MLOps** | Fixar sementes determinísticas (42); manifestos e logs com hashes SHA-256; concorrência segura; testes automatizados passando antes de commit. | **PASS**: Seed 42 fixada; manifesto com SHA-256 gerado; suíte de testes de regressão automatizada. |

## Project Structure

### Documentation (this feature)

```text
specs/014-dataset-particoes-quarentena/
├── spec.md                  # Especificação funcional e critérios de sucesso
├── plan.md                  # Este plano de implementação
├── research.md              # Decisões técnicas e fundamentos
├── data-model.md            # Esquemas de dados e estrutura do manifesto
├── contracts/
│   └── cli-contract.md      # Contrato de interface da CLI
├── quickstart.md            # Guia de execução e validação
├── checklists/
│   └── requirements.md      # Checklist de qualidade da especificação
└── tasks.md                 # Lista de tarefas de implementação (gerada via speckit-tasks)
```

### Source Code

```text
src/
├── dataset/
│   ├── __init__.py
│   ├── extractor.py         # Consulta SQL otimizada, extração dimensional e agregação vetorial
│   ├── quarantine.py        # Módulo de quarentena documental (regras e hashes da Feature 012)
│   └── partition.py         # Algoritmo de particionamento estratificado por grupos de id_tcu
scripts/
└── preparar_dataset_sprint6.py # CLI operacional de geração de datasets e manifesto
tests/
└── test_dataset_preparation.py # Testes de extração, quarentena, não-vazamento e integridade
```

**Structure Decision**: Criação do módulo modular `src/dataset/` para isolar as responsabilidades de extração dimensional, quarentena e particionamento, permitindo reuso direto nos passos de modelagem da Sprint 6 (Random Forest).

## Complexity Tracking

Sem violações à Constituição. Design mínimo e necessário para garantir ausência de vazamento de dados e cumprimento dos guardrails metodológicos.
