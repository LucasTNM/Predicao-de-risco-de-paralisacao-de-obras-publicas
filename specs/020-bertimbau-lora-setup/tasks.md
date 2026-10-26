# Tasks: Setup do Modelo (BERTimbau + LoRA) e Balanceamento de Classes (Sprint 7)

**Feature**: `020-bertimbau-lora-setup`  
**Status**: Concluído e auditado em 2026-10-19 — 9/9 tarefas finalizadas com sucesso.

## Phase 1: Setup e Perda Ponderada PyTorch (Card Balanceamento)
- [x] T001 [US2] Implementar `src/modeling/torch_loss.py` com fábrica de funções de perda ponderadas (`BCEWithLogitsLoss` com `pos_weight` e `CrossEntropyLoss` com tensor de pesos) e vinculação direta com `compute_class_weights`.
- [x] T002 [US2] Implementar testes unitários em `tests/test_torch_loss.py` comprovando que os pesos no PyTorch são matematicamente equivalentes aos calculados para o Scikit-Learn/LightGBM.

## Phase 2: Setup da Arquitetura BERTimbau + LoRA (Card Setup do Modelo)
- [x] T003 [US1] Implementar `src/modeling/bertimbau_lora.py` configurando o carregamento do BERTimbau cased, inicialização da cabeça de classificação binária e acoplamento de adaptadores LoRA via PEFT com congelamento da rede base.
- [x] T004 [US1] Implementar testes unitários em `tests/test_bertimbau_lora.py` verificando a fração de parâmetros treináveis (< 2%) e estrutura dos módulos adaptados (`query`, `value`).

## Phase 3: Dataset PyTorch e Teste de Fumaça na GPU (P1)
- [x] T005 [US1] Implementar `src/modeling/rag_dataset.py` com `WorkRAGDataset` e collator que consome o lote congelado `evidencias_rag_dev.jsonl` e tokeniza até 512 tokens com o tokenizer oficial do BERTimbau.
- [x] T006 [US1] Implementar `scripts/smoke_test_bertimbau.py` executando 1 época de treinamento na GPU local (RTX 5060) em 200 obras com rastreamento de perda, tempo e consumo máximo de VRAM.

## Phase 4: Execução, Relatório e Fechamento da Sprint 7 (P2)
- [x] T007 [US1] Executar `scripts/smoke_test_bertimbau.py` e gerar manifesto de execução com sucesso na GPU.
- [x] T008 [US3] Redigir `specs/020-bertimbau-lora-setup/report.md` com os parâmetros do modelo, consumo de VRAM e confirmação da viabilidade de treino completo na Sprint 8.
- [x] T009 Atualizar documentos de fechamento da Sprint 7 (`docs/Sprints/Sprint7.md` e `planos/Sprint7_Plano_de_Implementacao.md`) e rodar suíte de testes.

## Dependencies
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009.
