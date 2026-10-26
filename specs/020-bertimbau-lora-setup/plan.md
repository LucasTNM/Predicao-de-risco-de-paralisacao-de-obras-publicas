# Implementation Plan: 020-bertimbau-lora-setup

**Branch**: `020-bertimbau-lora-setup` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/020-bertimbau-lora-setup/spec.md`

## Summary

Configurar a arquitetura neural BERTimbau cased com adaptadores de baixo posto LoRA (PEFT) e cabeça de classificação para atuar como **Detector Binário de Risco** (Classe 0: Regular vs. Classe 1: Em Risco), integrando os fragmentos textuais recuperados pelo motor RAG da Feature 019. Implementar o tratamento de assimetria no PyTorch ligando diretamente os pesos de classe analíticos (`compute_class_weights`) à função de perda ponderada (`BCEWithLogitsLoss` com `pos_weight` ou `CrossEntropyLoss` com tensor de pesos). Executar teste de fumaça (*smoke test*) na GPU local RTX 5060 com precisão mista, comprovando que menos de 2% dos parâmetros são treináveis e que o consumo de memória respeita o limite de 8 GB.

## Technical Context

**Language/Version**: Python 3.14 (ambiente com GPU: `.venv-sprint4-gpu` com PyTorch 2.14 cu130, Hugging Face Transformers 4.57.6, PEFT 0.21.2, Accelerate 1.15.0).

**Primary Dependencies**: `torch`, `transformers`, `peft`, `accelerate`, `scikit-learn`, `numpy`.

**Model Base**: `neuralmind/bert-base-portuguese-cased` (revisão fixa idêntica à do chunking da Sprint 4).

**Testing**: `pytest` em `tests/test_torch_loss.py` e `tests/test_bertimbau_lora.py`; teste de fumaça em `scripts/smoke_test_bertimbau.py`.

**Target Platform**: Windows 11 local, NVIDIA GeForce RTX 5060 Laptop GPU (8 GB VRAM).

**Project Type**: Módulo PyTorch de modelagem neural supervisionada e script de teste de carga.

**Performance Goals**:
- Menos de 2% de parâmetros treináveis (< 2,2 milhões de parâmetros adaptados sobre os ~110M do BERTimbau).
- Uso de VRAM na GPU abaixo de 6 GB em batch size de 8 com gradient checkpointing ou acumulação.
- Teste de fumaça (1 época em 200 obras) executado em menos de 10 minutos.

**Constraints**:
- Acesso somente aos fragmentos congelados da Feature 019 (`evidencias_rag_dev.jsonl`).
- Congelamento estrito de todos os pesos pré-treinados do BERTimbau base.
- Pesos da função de perda derivados estritamente do conjunto de treino (sem vazamento).

## Constitution Check

| Princípio | Exigência | Situação no desenho |
| :--- | :--- | :---: |
| I. Fidedignidade e rótulo real | Rótulo binário reflete regularidade vs. risco sem contaminação sintética | PASS: insumos derivados do lote congelado da Feature 019 sem fichas sintéticas |
| II. Integridade semântica | Sequências respeitam o limite de 512 tokens sem truncamento destrutivo | PASS: truncamento e padding até 512 tokens gerenciados pelo tokenizer oficial |
| III. Consistência relacional | Obras sem texto recebem saída neutra/bypass tabular sem inferência cega | PASS: o classificador opera apenas sobre obras com evidência textual |
| IV. Reprodutibilidade | Hiperparâmetros LoRA, semente 42 e manifesto registrados | PASS: configuração serializada em JSON |

## Project Structure

### Documentation (this feature)

```text
specs/020-bertimbau-lora-setup/
├── spec.md
├── plan.md
├── tasks.md
├── checklists/requirements.md
└── report.md                  # Relatório de parâmetros treináveis, VRAM e teste de fumaça
```

### Source Code

```text
src/modeling/
├── torch_loss.py              # Fábrica de funções de perda ponderadas no PyTorch
├── bertimbau_lora.py          # Arquitetura BERTimbau + LoRA com contagem de parâmetros
└── rag_dataset.py             # Dataset e DataLoader PyTorch para lotes RAG

scripts/
└── smoke_test_bertimbau.py    # Script CLI para teste de fumaça na GPU com VRAM tracking

tests/
├── test_torch_loss.py         # Teste de equivalência dos pesos de perda
└── test_bertimbau_lora.py     # Testes da configuração LoRA e parâmetros treináveis
```
