# Tasks: 023-kaggle-llm-finetuning

**Feature**: `023-kaggle-llm-finetuning`  
**Input**: [`specs/023-kaggle-llm-finetuning/spec.md`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/specs/023-kaggle-llm-finetuning/spec.md), [`kaggle/PLANO_IMPLEMENTACAO_KAGGLE_LLM.md`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/PLANO_IMPLEMENTACAO_KAGGLE_LLM.md)  

---

## Phase 1: Auditoria Técnica e Exportação Zero-Leakage do Dataset para o Kaggle

- [x] T001 Criar pasta `kaggle/` e estruturar o plano de implementação e relatório de auditoria técnica `kaggle/PLANO_IMPLEMENTACAO_KAGGLE_LLM.md` (`v2.0`)
- [x] T002 Auditar e refatorar `kaggle/exportar_dataset_kaggle.py` (`AUD-01` a `AUD-03`): expurgar colunas administrativas pós-fato (`situacao_cadastral`, `causa_cadastral`, etc.) e proxies (`has_embedding`, `num_docs_validos`), corrigir formatação de metadados e embutir os embeddings oficiais `gte_c2` (768d) de `dados_processados/sprint7/embeddings_c2_sem_fichas.npz`
- [x] T003 Executar `kaggle/exportar_dataset_kaggle.py` (`v2.0`), gerar `treino_dev_completo.parquet` (15,40 MB, 14.522 obras, 3.088 com texto) e `teste_retido_completo.parquet` (4,40 MB, 3.632 obras, 739 com texto), validar hashes SHA-256 em `manifesto_dataset_kaggle.json` e metadados em `dataset-metadata.json`

---

## Phase 2: Construção e Validação Local do Notebook Unificado (`kaggle/experimento_kaggle_tcc.ipynb`)

- [x] T004 Implementar Seção 0 e Seção 1 em `kaggle/experimento_kaggle_tcc.ipynb`: detecção automática de ambiente (Local vs. Kaggle), asserções Zero-Leakage, construção das matrizes `C1` (6d) e `C2` (774d) e diagnóstico empírico de subword tokens (`BERTimbau` 512 vs. `Tropic-AI/moBERTo` 8.192)
- [x] T005 Implementar Seção 2 em `kaggle/experimento_kaggle_tcc.ipynb`: treinamento 5-fold OOF e avaliação no teste retido da Família 1 — Árvores de Decisão & Ensembles (`DummyMajority`, `RandomForest`, `LightGBM`, `XGBoost` e `CatBoost` em modos *Flat* e *Hierárquico em 2 Estágios* para `C1` e `C2`)
- [x] T006 Implementar Seção 3 em `kaggle/experimento_kaggle_tcc.ipynb`: motor PyTorch/HuggingFace de *Full Fine-Tuning* (100% dos parâmetros descongelados, FP16/BF16, Gradient Checkpointing, Cosine Warmup e ponderação de classes por dobra) para `neuralmind/bert-base-portuguese-cased` (512 tokens), `Tropic-AI/moBERTo` (2.048 tokens) e `jhu-clsp/mmBERT-base` (2.048 tokens)
- [x] T007 Implementar Seção 4 em `kaggle/experimento_kaggle_tcc.ipynb`: pipeline QLoRA 4-bit NF4 ($r=64, \alpha=128$) para LLMs Decoders de longo contexto em português (`Qwen/Qwen2.5-3B-Instruct` e `recogna-nlp/Bode-3.1-8B-Instruct-full`)
- [x] T008 Implementar Seção 5 em `kaggle/experimento_kaggle_tcc.ipynb`: calibração de *Late Fusion* estritamente em predições OOF, Bootstrap 95% CI ($B=1.000$), testes de hipótese pareados contra `Hierarquico_C2_LightGBM`, explicabilidade `TreeSHAP` e exportação automática de `tabela_comparativa_tcc.csv` e `resultados_kaggle_consolidados.json`
- [x] T009 Executar e validar `kaggle/experimento_kaggle_tcc.ipynb` no ambiente local GPU (`.venv-sprint4-gpu`) garantindo zero erros de sintaxe ou execução antes da importação no Kaggle Kernels

---

## Phase 3: Execução em Nuvem no Kaggle Kernels (GPU T4 x2 / P100)

- [ ] T010 Importar `kaggle/experimento_kaggle_tcc.ipynb` e o dataset `tcc-obras-tcu-multimodal` no Kaggle Kernels e executar o perfil `FULL_KAGGLE` completo nas 5 dobras
- [ ] T011 Consolidar os artefatos finais gerados pelo Kaggle em `specs/023-kaggle-llm-finetuning/report.md`
