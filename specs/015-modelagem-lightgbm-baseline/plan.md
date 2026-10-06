# Implementation Plan: 015-modelagem-lightgbm-baseline

**Branch**: `015-modelagem-lightgbm-baseline` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)

**Input**: Decisão do pesquisador de priorizar o LightGBM para alta dimensionalidade (768d) e eficiência de memória, mantendo o Random Forest como baseline inicial.

## Summary

Esta feature implementa o pipeline de modelagem supervisionada da Sprint 6 com foco em alta eficiência computacional e capacidade de lidar com alta dimensionalidade (768 dimensões contínuas de embeddings GTE combinadas com atributos tabulares). Constrói o baseline trivial (`DummyClassifier`), a referência clássica (`RandomForest`) e o modelo principal prioritário (`LightGBM`), aplicando ponderação balanceada de classes contra o desbalanceamento severo (91,7% Regular vs. 0,6% Deficiência Orçamentária). Avalia os modelos sob validação cruzada em 5 dobras agrupadas por obra (`id_tcu`) sem vazamento interno, mensurando tempo de treino, consumo de memória e métricas científicas robustas (Macro-F1, Balanced Accuracy, Recall por classe).

## Technical Context

**Language/Version**: Python 3.14.3 (ambiente virtual `.venv`)
**Primary Dependencies**: `lightgbm` (4.7.0), `duckdb` (1.5.6) para leitura ultrarrápida e compatível de Parquet, `numpy` (2.5.2), `pandas` (3.0.5).
**Storage**: Datasets Parquet em `dados_processados/sprint6/` (`dataset_treino_dev_2025.parquet` com 14.522 linhas e 768 dimensões de embedding).
**Testing**: `pytest` (8.3.5), testes unitários em `tests/test_modeling.py`.
**Target Platform**: Windows 11 x64 / Ambientes gratuitos em nuvem (GitHub Actions / Google Colab / VPS com baixa memória).
**Project Type**: Machine Learning Pipeline / CLI script / Python module.
**Performance Goals**:
- Treinamento do LightGBM com 768 dimensões e 14.522 observações em menos de 30 segundos.
- Consumo de memória RAM inferior a 1,5 GB durante todo o pipeline.
**Constraints**:
- O arquivo `dataset_teste_retido_2025.parquet` não deve ser tocado durante o desenvolvimento.
- Resiliência operacional: uso da API de Booster do LightGBM e implementação pura em NumPy para métricas e divisão de dobras, contornando bloqueios de DLLs de terceiros pelo Smart App Control do Windows.
- Preservação estrita dos princípios da Constituição (Artigos I, II, III e IV).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Exigência Constitucional | Status no Design |
| :--- | :--- | :---: |
| **I. Fidedignidade histórica e rótulo real** | Alvo histórico até 2025 com 4 classes causais (0, 1, 2, 3); dados de 2026 vedados no treino; obras pendentes (NULL) excluídas do treino causal. | **PASS**: O pipeline consome estritamente `dataset_treino_dev_2025.parquet`. Casos pendentes e dados de 2026 permanecem intocados em seus arquivos segregados. |
| **II. Integridade semântica dos documentos** | Embeddings derivados dos textos válidos; exclusão de quarentena mantida. | **PASS**: Consome a partição gerada na Feature 014, onde os 36 documentos DNIT da quarentena já foram previamente expurgados. |
| **III. Consistência relacional e dimensional** | 1 observação por obra/data-base; sem distorção ou multiplicação de valores monetários. | **PASS**: O dataset de desenvolvimento possui correspondência estrita 1:1 por obra e valores financeiros normalizados. |
| **IV. Reprodutibilidade de ML e MLOps** | Fixar sementes determinísticas (42); registrar tempos, métricas e parâmetros em manifesto JSON auditável; testes automatizados passando. | **PASS**: Semente 42 fixada em todos os classificadores e splitters; resultados persistidos em JSON e Markdown. |

## Project Structure

### Documentation (this feature)

```text
specs/015-modelagem-lightgbm-baseline/
├── spec.md                  # Especificação funcional e requisitos
├── plan.md                  # Este plano de implementação
├── tasks.md                 # Lista ordenada de tarefas de implementação
└── report.md                # Relatório final de execução e benchmark de modelos
```

### Source Code

```text
src/
└── modeling/
    ├── __init__.py
    ├── loader.py            # Carregamento seguro via DuckDB, matrizes de features e alvos
    ├── metrics.py           # Macro-F1, Balanced Accuracy, Recall por classe e Matriz de Confusão em NumPy puro
    ├── splitter.py          # Particionador de validação cruzada agrupado por id_tcu (5 dobras)
    ├── baselines.py         # DummyClassifier e baseline Random Forest
    ├── lightgbm_engine.py   # Motor de treinamento e predição do LightGBM com pesos balanceados
    └── evaluator.py         # Orquestrador de experimentos comparativos (tempo, RAM, métricas)

scripts/
└── treinar_sprint6.py       # CLI executável de treinamento e benchmarking da Sprint 6

tests/
└── test_modeling.py         # Suíte de testes unitários para o módulo de modelagem
```

## Structure Decisions

* **DuckDB como I/O de dados**: DuckDB lê nativamente arquivos Parquet de 32 MB com arrays vetoriais em < 0,5s sem exigir compilação de C extensions não assinadas, garantindo execução em qualquer plataforma.
* **Métricas em NumPy Puro**: Implementação autocontida de F1-macro, Balanced Accuracy e Confusion Matrix elimina dependências externas e garante consistência numérica idêntica à do scikit-learn.
* **LightGBM Core Booster API**: Utilização direta do motor nativo `lightgbm.train`, garantindo máxima velocidade de execução, uso de memória reduzido e total compatibilidade.
