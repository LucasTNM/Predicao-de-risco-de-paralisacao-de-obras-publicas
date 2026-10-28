# Instruções Operacionais: Pipeline Auditado de Experimento no Kaggle (`v2.0`)

Este diretório contém o dataset multimodal auditado (livre de vazamento de alvo), o script de exportação reproduzível, o plano técnico-científico homologado e o **Jupyter Notebook completo** para comparação entre Árvores de Decisão Multimodais (`C1`/`C2`), Encoders Bidirecionais de Contexto Longo em Português (*Full Fine-Tuning*) e LLMs Decoders (*QLoRA*).

---

## 1. Estrutura de Arquivos em `kaggle/`

1. [`experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb): **Jupyter Notebook principal completo, modular e autocontido**, pronto para:
   - Inspeção, ajuste e validação direta no ambiente local (VS Code / WSL / GPU local);
   - Importação direta (*File -> Import Notebook*) no **Kaggle Kernels** (1x ou 2x Tesla T4 16GB / P100 16GB).
2. [`PLANO_IMPLEMENTACAO_KAGGLE_LLM.md`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/PLANO_IMPLEMENTACAO_KAGGLE_LLM.md): Relatório de Auditoria Técnica (`AUD-01` a `AUD-05`), medição empírica da janela de tokens, catálogo de modelos verificados e dimensionamento de VRAM.
3. [`exportar_dataset_kaggle.py`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/exportar_dataset_kaggle.py): Script de exportação auditado (`v2.0`) que expurga colunas administrativas pós-fato e embute os embeddings oficiais `gte_c2` (768d) da Sprint 7/8.
4. `datasets_preparados/`:
   - `treino_dev_completo.parquet` (**15,40 MB**): 14.522 obras de treino/dev (3.088 com texto autêntico), 6 atributos tabulares `c1_sem_proxies`, vetor `gte_c2` (768d) e 5 dobras `fold_cv` agrupadas por `id_tcu`.
   - `teste_retido_completo.parquet` (**4,40 MB**): 3.632 obras do teste retido congelado (739 com texto autêntico) e vetor `gte_c2` (768d).
   - `manifesto_dataset_kaggle.json`: Hashes SHA-256 e metadados de auditoria.
   - `dataset-metadata.json`: Manifesto para publicação via Kaggle CLI.

---

## 2. Como Executar Localmente vs. no Kaggle

### 2.1 Execução e Validação Local (VS Code / Jupyter)
1. Abra [`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb) no VS Code.
2. Selecione o kernel Python do ambiente GPU (`.venv-sprint4-gpu`).
3. Na **Célula de Configuração Global (Seção 0)**, a flag `EXECUTION_MODE` detecta automaticamente o ambiente:
   - `"LOCAL_SMOKE"` (padrão local rápido): executa 100% da auditoria de dados, diagnóstico de tokens, todos os modelos de árvores (`Dummy`, `RandomForest`, `LightGBM`, `XGBoost`, `CatBoost` em modos *Flat* e *Hierárquico C1/C2*), um ciclo rápido de validação do pipeline PyTorch/HuggingFace e a consolidação estatística + XAI.
   - `"FULL_KAGGLE"` (padrão quando detecta `/kaggle/input` ou quando acionado manualmente): executa o *Full Fine-Tuning* completo por 5 dobras dos encoders (`BERTimbau`, `Tropic-AI/moBERTo`, `jhu-clsp/mmBERT-base`), o ajuste QLoRA dos decoders (`Qwen/Qwen2.5-3B-Instruct`, `recogna-nlp/Bode-3.1-8B-Instruct-full`) e o Bootstrap completo ($B=1.000$).

### 2.2 Importação e Execução no Kaggle Kernels
1. Acesse [kaggle.com/datasets](https://www.kaggle.com/datasets), clique em **"New Dataset"**, nomeie como `tcc-obras-tcu-multimodal` (Privado) e faça upload dos arquivos de `kaggle/datasets_preparados/`:
   - `treino_dev_completo.parquet`
   - `teste_retido_completo.parquet`
   - `manifesto_dataset_kaggle.json`
2. Crie um novo Notebook no Kaggle, clique em **File -> Import Notebook** e envie [`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb).
3. No painel lateral direito do Kaggle:
   - Em **Inputs**, anexe o dataset `tcc-obras-tcu-multimodal`;
   - Em **Session Options -> Accelerator**, selecione **GPU T4 x2** (ou **GPU P100**);
   - Ative **Internet: On** (para baixar os checkpoints públicos do Hugging Face).
4. Clique em **Save Version -> Save & Run All (Commit)** para rodar em segundo plano e baixar ao final os artefatos `resultados_kaggle_consolidados.json` e `tabela_comparativa_tcc.csv`.
