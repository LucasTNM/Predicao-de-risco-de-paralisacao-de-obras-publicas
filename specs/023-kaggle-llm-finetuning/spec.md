# Feature Specification: 023-kaggle-llm-finetuning (Auditado v2.0)

**Feature Branch**: `023-kaggle-llm-finetuning`  
**Created**: 2026-10-26  
**Updated (Audit v2.0)**: 2026-10-27  
**Status**: Homologado Localmente (`kaggle/experimento_kaggle_tcc.ipynb`)  
**Input**: Auditoria Técnica e Plano de Implementação Kaggle — *Full Fine-Tuning* de Encoders Bidirecionais de Longo Contexto em Português (`Tropic-AI/moBERTo`, `jhu-clsp/mmBERT-base`, `Itau-Unibanco/NorBERTo-base` vs. `neuralmind/bert-base-portuguese-cased`), *QLoRA* de Decoders PT-BR (`Qwen/Qwen2.5-3B-Instruct`, `recogna-nlp/Bode-3.1-8B-Instruct-full`) e Benchmark Exaustivo contra Árvores de Decisão Multimodais (`LightGBM`, `XGBoost`, `CatBoost`, `RandomForest`).

---

## User Scenarios & Testing

### User Story 1 - Exportação Auditada e Zero-Leakage do Dataset para o Kaggle (Priority: P1) 🎯
Como pesquisador, quero exportar o dataset multimodal de treino/dev (14.522 obras, 3.088 com texto autêntico) e teste retido congelado (3.632 obras, 739 com texto autêntico) em arquivos `.parquet` autocontidos, livres de qualquer coluna pós-fato (*target leakage*) ou proxy operacional, embutindo os vetores oficiais `gte_c2` (768d) da Sprint 7/8 e as 5 dobras `fold_cv` agrupadas por `id_tcu`.

**Independent Test**: Script [`kaggle/exportar_dataset_kaggle.py`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/exportar_dataset_kaggle.py) gera `treino_dev_completo.parquet` e `teste_retido_completo.parquet` com manifesto SHA-256 e passa em todas as asserções de disjunção de `id_tcu` e ausência de colunas proibidas.

---

### User Story 2 - Benchmark Exaustivo de Árvores de Decisão e Ensembles Multimodais (`C1` vs. `C2`) (Priority: P1)
Como pesquisador, quero avaliar `DummyMajority`, `RandomForest`, `LightGBM`, `XGBoost` e `CatBoost` tanto em configuração plana (*Flat*) quanto na arquitetura *Hierárquica em Dois Estágios* sobre os espaços `C1` (6d tabular limpo) e `C2` (774d multimodal com `gte_c2`), gerando predições *out-of-fold* (`OOF`) e predições no teste retido congelado.

**Independent Test**: Seção 2 de [`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb) executada de ponta a ponta reproduzindo o campeão `Hierarquico_C2_LightGBM` e comparando-o com `Hierarquico_C2_CatBoost` e `Hierarquico_C2_XGBoost`.

---

### User Story 3 - Full Fine-Tuning de Encoders e Diagnóstico Empírico da Janela de Contexto (512 vs. 2.048 / 8.192 Tokens) (Priority: P1)
Como pesquisador, quero quantificar empiricamente a perda de tokens por truncamento em 512 tokens (66,3% dos tokens descartados em 97,2% das obras) e executar o *Full Fine-Tuning* (100% dos parâmetros descongelados) do `BERTimbau` (512 tokens) frente aos modelos **ModernBERT em português e multilíngues** (`Tropic-AI/moBERTo` e `jhu-clsp/mmBERT-base`, janela nativa de 8.192 tokens operando em 2.048 tokens com 0% de perda relevante).

**Independent Test**: Seções 1 e 3 de [`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb) validam a tokenização e o pipeline PyTorch/HuggingFace de *Full Fine-Tuning* com ponderação de classe por dobra, mixed precision e gradient checkpointing.

---

### User Story 4 - Fine-Tuning de Decoders em Português com QLoRA 4-bit (`Qwen 2.5` e `Bode 3.1`) (Priority: P2)
Como pesquisador, quero ajustar com QLoRA 4-bit NF4 ($r=64, \alpha=128$) modelos decoders de longo contexto em português (`Qwen/Qwen2.5-3B-Instruct` e `recogna-nlp/Bode-3.1-8B-Instruct-full`), avaliando sua capacidade discriminativa no conjunto de obras com texto.

**Independent Test**: Seção 4 de [`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb) implementa o treinamento `BitsAndBytesConfig` + `LoraConfig` pronto para execução nas GPUs T4 do Kaggle.

---

### User Story 5 - Fusão Híbrida Calibrada em OOF, Bootstrap ($B=1.000$) e XAI (Priority: P1)
Como autor do TCC, quero calibrar o ensemble híbrido exclusivamente nas predições OOF de `treino_dev` e avaliar todos os modelos no teste retido com Intervalos de Confiança a 95% via Bootstrap ($B=1.000$), $p$-values pareados contra `Hierarquico_C2_LightGBM`, atribuição `TreeSHAP` e exportação automática de `tabela_comparativa_tcc.csv` e `resultados_kaggle_consolidados.json`.

**Independent Test**: Seção 5 de [`kaggle/experimento_kaggle_tcc.ipynb`](file:///c:/Users/lucas/OneDrive/Documentos/TCC/kaggle/experimento_kaggle_tcc.ipynb) gera os artefatos finais validados localmente.
