# Implementation Plan: 017-avaliacao-teste-retido-sprint6

**Branch**: `017-avaliacao-teste-retido-sprint6` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Execução da avaliação cega final da Sprint 6 sobre o dataset de teste retido (`dataset_teste_retido_2025.parquet`) via SpecKit.

## Summary

Esta feature encerra formalmente a modelagem preditiva da Sprint 6 realizando a avaliação cega e definitiva dos modelos supervisionados construídos nas Features 015 e 016 sobre as 3.632 obras reservadas de teste (`dataset_teste_retido_2025.parquet`). Valida previamente a inexistência de vazamento de dados (`intersecao_obras = 0`), treina os modelos eleitos em 100% da partição de desenvolvimento (14.522 obras), infere as classes sobre a partição de teste e confronta as métricas de teste cego contra as métricas de validação cruzada interna, documentando os resultados finais da Sprint 6.

## Technical Context

**Language/Version**: Python 3.14.3 (ambiente virtual `.venv`)
**Primary Dependencies**: `lightgbm` (4.7.0), `duckdb` (1.5.6), `numpy` (2.5.2), `pandas` (3.0.5).
**Storage**:
- Treino: `dados_processados/sprint6/dataset_treino_dev_2025.parquet` (14.522 observações).
- Teste: `dados_processados/sprint6/dataset_teste_retido_2025.parquet` (3.632 observações).
**Testing**: `pytest` (8.3.5), testes em `tests/test_final_evaluation.py`.
**Target Platform**: Windows 11 x64 / Ambientes gratuitos em nuvem.
**Performance Goals**:
- Treinamento integral no desenvolvimento e inferência no teste concluídos em menos de 45 segundos.
**Constraints**:
- O dataset de teste é somente leitura; nenhuma modificação ou reamostragem sintética é permitida.
- Os parâmetros de imputação e codificação categórica devem ser estritamente aprendidos no desenvolvimento.
- Preservação estrita dos princípios da Constituição (Artigos I, II, III e IV).

## Constitution Check

| Princípio | Exigência Constitucional | Status no Design |
| :--- | :--- | :---: |
| **I. Fidedignidade histórica e rótulo real** | Avaliação cega sem vazamento; distribuição natural do teste preservada sem balanceamento artificial. | **PASS**: O teste retido possui a proporção natural (91,7% Regular vs. 0,6% Orçamentária) sem qualquer SMOTE ou descarte. |
| **II. Integridade semântica dos documentos** | Embeddings derivados dos textos válidos; quarentena preservada. | **PASS**: Ambos os conjuntos provêm do particionamento auditado da Feature 014. |
| **III. Consistência relacional e dimensional** | 1 observação por obra; cardinalidade 1:1 mantida. | **PASS**: Teste com exatamente 3.632 obras únicas. |
| **IV. Reprodutibilidade de ML e MLOps** | Semente 42 fixada; manifesto de saída com estatísticas e parâmetros. | **PASS**: Pipeline 100% determinístico e auditável. |

## Project Structure

### Documentation (this feature)

```text
specs/017-avaliacao-teste-retido-sprint6/
├── spec.md                  # Especificação e requisitos da avaliação cega
├── plan.md                  # Este plano de implementação
├── tasks.md                 # Lista de tarefas ordenadas
└── report.md                # Relatório final definitivo do teste retido para a dissertação
```

### Source Code

```text
scripts/
└── avaliar_teste_retido_sprint6.py # CLI de treinamento integral e inferencia no teste cego

tests/
└── test_final_evaluation.py        # Testes unitarios e de integridade do pipeline de avaliacao final
```
