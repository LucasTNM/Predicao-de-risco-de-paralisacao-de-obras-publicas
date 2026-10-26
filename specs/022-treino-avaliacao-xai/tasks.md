# Tasks: Execução do Treinamento BERTimbau + LoRA, Avaliação no Teste Retido e XAI (Feature 022 / Sprint 8)

**Feature**: `022-treino-avaliacao-xai`  
**Input**: Design documents from `specs/022-treino-avaliacao-xai/` (`spec.md`, `plan.md`)  
**Prerequisites**: Lotes RAG regenerados em `dados_processados/sprint7/evidencias_rag_dev.jsonl` (`3.088` obras com texto autêntico) e `evidencias_rag_teste.jsonl` (`739` obras com texto autêntico), matrizes `embeddings_c2_sem_fichas.npz` atualizadas (`T025`).

---

## Phase 1: Setup & Módulo XAI / Avaliação Estatística (Foundational)

- [x] T001 Implementar `src/modeling/xai.py` contendo extração de pesos de atenção do *encoder* BERTimbau (`extract_attention_and_grad_attribution`), atribuição por gradiente (`Input x Gradient`), teste de fidelidade por deleção de tokens (`run_deletion_faithfulness_test`), auditoria de termos proibidos nos top tokens e extração de valores SHAP exatos (`pred_contrib=True`) para o modelo LightGBM
- [x] T002 Criar e executar testes unitários em `tests/test_xai_sprint8.py` validando o cálculo de atribuição, teste de deleção, auditoria de termos proibidos e intervalos de confiança via bootstrap (`4 passed`)

---

## Phase 2: User Story 1 - Ajuste Fino BERTimbau + LoRA com Validação Cruzada Agrupada (Priority: P1) 🎯

- [x] T003 [US1] Implementar em `scripts/treinar_bertimbau_sprint8.py` o treinamento em 5 dobras agrupadas por `id_tcu` (`StratifiedGroupSplitter`) sobre as `3.088` obras com evidência textual autêntica de `evidencias_rag_dev.jsonl`, com perda ponderada por dobra, *early stopping*, registro de Macro-F1, Balanced Accuracy, MCC, AUC-PR e geração das predições *out-of-fold* (OOF) — **Concluído: 5 dobras executadas na RTX 5060; OOF Binário Macro-F1: 0.6278, MCC: 0.2556; OOF Multiclasse Macro-F1: 0.3586, MCC: 0.1305**
- [x] T004 [US1] Treinar o modelo final pré-registrado BERTimbau + LoRA sobre `evidencias_rag_dev.jsonl` usando o número ótimo de épocas selecionado na validação cruzada (3 épocas) e persistir os adaptadores e manifesto SHA-256 em `modelos/sprint8_bertimbau_lora/` — **Concluído: adaptadores salvos em `modelos/sprint8_bertimbau_lora/binario/` e `modelos/sprint8_bertimbau_lora/multiclasse/` (591.362 parâmetros treináveis, 0,54% da rede)**

---

## Phase 3: User Story 2 - Avaliação Comparativa Única no Conjunto de Teste Retido (Priority: P1)

- [x] T005 [US2] Avaliar uma única vez no conjunto de teste retido: (a) nas `739` obras com texto autêntico (`BERTimbau_LoRA`, `LightGBM_Tabular_C1`, `Hierarquico_C2`, `Sistema_Hibrido_BERTimbau_C2`) e (b) na população integral de `3.632` obras (`Dummy`, `RandomForest_C1`, `LightGBM_C1`, `Hierarquico_C1`, `LightGBM_C2`, `Hierarquico_C2`, `Sistema_Hibrido_BERTimbau_C2`), calculando Macro-F1, Balanced Accuracy, MCC, Recall/Precisão por classe, curvas PR/AUC-PR, matriz de confusão, IC 95% via bootstrap ($B=1.000$) e teste pareado — **Concluído em `scripts/avaliar_hibrido_xai_sprint8.py`: `Hierarquico_C2_Texto_Autentico` campeão absoluto com Macro-F1: 0.5377 [0.5015, 0.5743], MCC: 0.5508; Sistema Híbrido com Macro-F1: 0.5366, sem diferença estatisticamente significante (p = 0.516)**

---

## Phase 4: User Story 3 - Explicabilidade (XAI) com Verificação de Fidelidade e SHAP (Priority: P2)

- [x] T006 [US3] Gerar explicações XAI completas (atenção do *encoder*, atribuição por gradiente, teste de deleção comparativo contra máscara aleatória, auditoria de termos proibidos e valores SHAP do LightGBM) para $\ge 60$ obras do teste retido estratificadas pelas 4 classes, salvando os artefatos em `dados_processados/sprint8/xai_explicacoes_teste.json` — **Concluído: 64 obras explicadas; fidelidade por deleção de 60,94% (drop top-k +0.2288 vs aleatório +0.2243); 0 alertas de vazamento de termos proibidos; ranking global TreeSHAP consolidado**

---

## Phase 5: Relatório Final e Convergência SpecKit

- [x] T007 Consolidar todas as tabelas, intervalos de confiança, curvas PR, métricas de fidelidade XAI e conclusões científicas em `specs/022-treino-avaliacao-xai/report.md` e atualizar `specs/021-revisao-expansao-coleta/report.md` e `tasks.md` (`T026`) — **Concluído: `specs/022-treino-avaliacao-xai/report.md` gerado com rastreabilidade completa**
