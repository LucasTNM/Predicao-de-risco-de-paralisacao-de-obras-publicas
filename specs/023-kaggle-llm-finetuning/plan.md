# Implementation Plan: 023-kaggle-llm-finetuning (Auditado v2.0)

**Feature**: `023-kaggle-llm-finetuning`  
**Spec**: [`specs/023-kaggle-llm-finetuning/spec.md`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/specs/023-kaggle-llm-finetuning/spec.md)  
**Detailed Plan**: [`kaggle/PLANO_IMPLEMENTACAO_KAGGLE_LLM.md`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/PLANO_IMPLEMENTACAO_KAGGLE_LLM.md)  
**Executable Notebook**: [`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb)  

---

## 1. Resumo Arquitetural (v2.0 Pós-Auditoria)

1. **Exportação Autocontida e Zero-Leakage ([`kaggle/exportar_dataset_kaggle.py`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/exportar_dataset_kaggle.py))**:
   - Gera `treino_dev_completo.parquet` (14.522 obras, 3.088 com texto autêntico) e `teste_retido_completo.parquet` (3.632 obras, 739 com texto autêntico).
   - Remove todas as colunas pós-fato (`situacao_cadastral`, `causa_cadastral`, `origem_rotulo`, `status_rotulagem`) e proxies operacionais (`has_embedding`, `num_docs_validos`, `num_chunks_validos`).
   - Embute na coluna `gte_c2` os embeddings densos oficiais de 768 dimensões (`dados_processados/sprint7/embeddings_c2_sem_fichas.npz`), preservando os 5 folds agrupados por `id_tcu` (`fold_cv`).

2. **Notebook Único Modular e Portável ([`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb))**:
   - **Seção 0**: Setup determinístico (`SEED = 42`), detecção automática Local vs. Kaggle (`IS_KAGGLE`, `EXECUTION_MODE`) e auditoria automatizada de integridade e disjunção de `id_tcu`.
   - **Seção 1**: Diagnóstico empírico de subword tokens comprovando que `neuralmind/bert-base-portuguese-cased` (512 tokens) trunca **97,2% das obras** e descarta **66,3% dos tokens**, enquanto `Tropic-AI/moBERTo` (ModernBERT PT-BR, 8.192 tokens) cobre **99,95% das obras em 2.048 tokens** e **100% em 4.096 tokens**.
   - **Seção 2**: Família 1 — Árvores de Decisão e Ensembles (`DummyMajority`, `RandomForest`, `LightGBM`, `XGBoost` e `CatBoost` em modos *Flat* e *Hierárquico em 2 Estágios* sobre `C1` e `C2`).
   - **Seção 3**: Família 2 — *Full Fine-Tuning* (100% dos parâmetros descongelados) de Encoders Bidirecionais (`neuralmind/bert-base-portuguese-cased` em 512 tokens vs. `Tropic-AI/moBERTo` e `jhu-clsp/mmBERT-base` em 2.048 tokens).
   - **Seção 4**: Família 3 — *QLoRA 4-bit NF4* ($r=64, \alpha=128$) para Decoders em Português (`Qwen/Qwen2.5-3B-Instruct` e `recogna-nlp/Bode-3.1-8B-Instruct-full`).
   - **Seção 5**: Calibração de *Late Fusion* em predições OOF, Bootstrap ($B=1.000$), testes de hipótese pareados, explicabilidade `TreeSHAP` e exportação de `tabela_comparativa_tcc.csv` e `resultados_kaggle_consolidados.json`.
