# Implementation Plan: 022-treino-avaliacao-xai

**Branch**: `022-treino-avaliacao-xai` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-treino-avaliacao-xai/spec.md`

## Summary

Executar o treinamento supervisionado completo do classificador **BERTimbau + LoRA** (`neuralmind/bert-base-portuguese-cased`, $r=16, \alpha=32$, `query` + `value`, $0,54\%$ de parâmetros treináveis) sobre o novo corpus expandido de documentos governamentais autênticos (`3.088` obras com texto em `evidencias_rag_dev.jsonl`, zero fichas sintéticas), usando validação cruzada estratificada e agrupada por `id_tcu` em 5 dobras com parada antecipada (*early stopping*) e perda ponderada por classe. Em seguida, treinar o modelo final pré-registrado em `treino_dev`, realizar a **avaliação comparativa única no conjunto de teste retido** (`3.632` obras totais; `739` obras com texto autêntico em `evidencias_rag_teste.jsonl`) integrando o **Sistema Híbrido (BERTimbau + LoRA + LightGBM Hierárquico C2)** com intervalos de confiança de 95% via *bootstrap* ($B=1.000$) e curvas PR por classe. Por fim, executar o módulo de **Explicabilidade (XAI)** combinando pesos de atenção do *encoder*, atribuição por gradiente (*Integrated Gradients / Input $\times$ Gradient*), valores **SHAP** exatos para o LightGBM, **teste de fidelidade por deleção de tokens** e auditoria automática de termos proibidos em $\ge 60$ obras do teste retido.

## Technical Context

**Language/Version**: Python 3.14 (`.venv-sprint4-gpu` com PyTorch 2.14.0+cu130, Transformers 4.57.6, PEFT 0.21.2, Accelerate 1.15.0, Scikit-Learn, LightGBM).

**Primary Dependencies**: `torch`, `transformers`, `peft`, `scikit-learn`, `lightgbm`, `numpy`, `pandas`, `pyarrow`.

**Model Base**: `neuralmind/bert-base-portuguese-cased` (LoRA $r=16, \alpha=32, \text{dropout}=0.1$).

**Testing**: `pytest` em `tests/test_xai_sprint8.py`.

**Target Platform**: Windows 11 local, NVIDIA GeForce RTX 5060 Laptop GPU (8 GB VRAM).

**Performance Goals**:
- Treinamento completo (5 dobras CV + modelo final) em $< 30$ minutos na GPU RTX 5060 com AMP (`fp16`).
- Uso de VRAM $< 4,5$ GB.
- Explicações XAI + teste de deleção para $\ge 60$ obras de teste em $< 5$ minutos.

## Constitution Check

| Princípio | Exigência | Situação no desenho |
| :--- | :--- | :---: |
| I. Fidedignidade e rótulo real | Zero fichas sintéticas; auditoria de termos proibidos nos top tokens de XAI | PASS: lote `evidencias_rag_*.jsonl` contém 100% documentos autênticos |
| II. Integridade semântica | Janela de até 512 tokens sobre fragmentos RAG ranqueados por cosseno | PASS: `WorkRAGDataset` preserva fragmentos top-4 |
| III. Consistência relacional | Zero interseção de `id_tcu` entre treino/validação e teste retido | PASS: `StratifiedGroupSplitter` por `id_tcu` |
| IV. Reprodutibilidade | Semente 42 fixa, manifesto SHA-256 dos adaptadores LoRA e métricas JSON | PASS: pesos LoRA salvos em `modelos/sprint8_bertimbau_lora/` |

## Project Structure

### Documentation (this feature)

```text
specs/022-treino-avaliacao-xai/
├── spec.md
├── plan.md
├── tasks.md
├── checklists/requirements.md
└── report.md                  # Relatório consolidado da Sprint 8 (Treino, Avaliação e XAI)
```

### Source Code

```text
src/modeling/
├── bertimbau_lora.py          # Arquitetura BERTimbau + LoRA (binária e multiclasse)
├── rag_dataset.py             # Dataset PyTorch para lotes RAG
├── torch_loss.py              # Perda ponderada analítica por dobra
└── xai.py                     # Atenção do encoder, Input x Gradient / IG, Deletion Test e SHAP

scripts/
└── executar_sprint8_bertimbau_xai.py  # Orquestrador ponta a ponta: 5-fold CV, Modelo Final, Teste Retido (3.632 obras) e XAI (>=60 obras)

tests/
└── test_xai_sprint8.py        # Testes unitários para métricas de bootstrap, XAI e teste de deleção
```
