# Implementation Plan: 016-classificacao-hierarquica-dois-estagios

**Branch**: `016-classificacao-hierarquica-dois-estagios` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Decomposição hierárquica em dois estágios para tratamento do desbalanceamento extremo da Classe 2 (0,57% da base).

## Summary

Esta feature implementa e valida uma arquitetura de classificação hierárquica em dois estágios baseada em LightGBM para predizer risco e causas de paralisação em obras públicas:
- **Estágio 1 (Detector de Risco - Binário)**: Discrimina Obras Regulares (Classe 0: 13.319 casos) de Obras com Paralisação/Risco (Classes 1, 2 e 3 agrupadas: 1.203 casos), operando sob contraste binário equilibrado via `scale_pos_weight`.
- **Estágio 2 (Atribuidor Causal - Multiclasse Condicional)**: Opera estritamente no subespaço das obras paralisadas (1.203 casos), classificando entre Deficiência Técnica (1), Deficiência Orçamentária (2) e Abandono (3). Neste subespaço, a Classe 2 representa ~7% da amostra (e não 0,57%), permitindo aos pesos de classe atuarem com máxima eficácia.
- **Inferência Conjunta**: Combinação probabilística marginalizada ($P_{total} = P_{risco} \times P_{causa}$) e cascata determinística com calibração de limiares operacionais.
- **Validação Cruzada Agrupada**: Avaliação nas mesmas 5 dobras agrupadas por `id_tcu` da Feature 015, comparando diretamente o ganho no Recall da Classe 2 e Macro-F1.

## Technical Context

**Language/Version**: Python 3.14.3 (ambiente virtual `.venv`)
**Primary Dependencies**: `lightgbm` (4.7.0), `duckdb` (1.5.6), `numpy` (2.5.2), `pandas` (3.0.5).
**Storage**: `dados_processados/sprint6/dataset_treino_dev_2025.parquet` (14.522 observações, 777 atributos).
**Testing**: `pytest` (8.3.5), testes unitários em `tests/test_hierarchical_modeling.py`.
**Target Platform**: Windows 11 x64 / Infraestrutura gratuita em nuvem (baixo consumo de RAM e CPU).
**Performance Goals**:
- Treinamento dos dois estágios em 5 dobras concluído em menos de 90 segundos.
- Elevação do Recall da Classe 2 em relação ao modelo de estágio único da Feature 015 (que foi de 2,41%).
**Constraints**:
- O arquivo `dataset_teste_retido_2025.parquet` permanece intocado (Blind Test).
- Zero vazamento de obras (`id_tcu`) entre treino e validação interna em todas as dobras.
- Respeito aos quatro artigos da Constituição do Projeto.

## Constitution Check

| Princípio | Exigência Constitucional | Status no Design |
| :--- | :--- | :---: |
| **I. Fidedignidade histórica e rótulo real** | Classes 0, 1, 2 e 3 preservadas conforme taxonomia; dados de 2026 vedados; sem preenchimento forçado de causas ausentes. | **PASS**: O modelo utiliza exatamente os rótulos homologados de 2025 na partição de desenvolvimento. |
| **II. Integridade semântica dos documentos** | Embeddings derivados dos textos válidos sem documentos de quarentena. | **PASS**: Utiliza o dataset da Feature 014 que já expurgou os 36 documentos DNIT. |
| **III. Consistência relacional e dimensional** | 1 observação por obra; sem duplicação de dados cadastrais. | **PASS**: Cardinalidade estrita 1:1 mantida. |
| **IV. Reprodutibilidade de ML e MLOps** | Fixar sementes determinísticas (42); registrar manifesto JSON com métricas e parâmetros auditáveis. | **PASS**: Semente 42 registrada em ambos os estágios e relatórios gerados automaticamente. |

## Project Structure

### Documentation (this feature)

```text
specs/016-classificacao-hierarquica-dois-estagios/
├── spec.md                  # Especificação funcional e requisitos
├── plan.md                  # Este plano de implementação
├── tasks.md                 # Lista de tarefas de implementação
└── report.md                # Relatório final comparativo contra a Feature 015
```

### Source Code

```text
src/
└── modeling/
    ├── hierarchical.py      # BinaryRiskDetector, ConditionalCausalClassifier e TwoStageHierarchicalClassifier
    ├── evaluator.py         # Orquestrador estendido para suportar modelos hierarquicos
    └── ...                  # Modulos reutilizados (loader, metrics, splitter, lightgbm_engine)

scripts/
└── treinar_hierarquico_sprint6.py # CLI de treinamento e comparativo da arquitetura hierarquica

tests/
└── test_hierarchical_modeling.py  # Testes unitarios da decomposicao hierarquica
```
