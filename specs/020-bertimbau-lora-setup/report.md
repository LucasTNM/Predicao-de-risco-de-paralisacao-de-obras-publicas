# Relatório Técnico: Setup BERTimbau + LoRA e Balanceamento de Classes (Sprint 7)

**Feature**: `020-bertimbau-lora-setup`  
**Data de Conclusão**: 2026-10-19  
**Status**: Concluído e Auditado com Sucesso  

---

## 1. Resumo Executivo

A Feature 020 concluiu com êxito o setup da arquitetura neural **BERTimbau + LoRA** e o tratamento analítico de desbalanceamento de classes no PyTorch, atendendo integralmente aos dois cards finais do backlog da Sprint 7:

1. **Balanceamento de Classes (Tratamento da Assimetria)**:
   - Implementado o módulo `src/modeling/torch_loss.py`, que conecta os pesos analíticos calculados por dobra (`compute_class_weights` com fórmula $N / (K \cdot N_c)$) à função de perda do PyTorch (`CrossEntropyLoss` ponderada ou `BCEWithLogitsLoss` com `pos_weight = scale_pos_weight`).
   - Garante a penalização matemática rigorosa de falsos negativos na detecção de obras em risco (classe minoritária).
2. **Setup do Modelo (BERTimbau + LoRA)**:
   - Configurada a arquitetura `neuralmind/bert-base-portuguese-cased` com cabeça de classificação binária (Regular vs. Em Risco) e adaptadores LoRA acoplados aos módulos de atenção `query` e `value`.
   - O backbone do transformer foi 100% congelado, atingindo **apenas 0,54% de parâmetros treináveis**, cumprindo com ampla folga a restrição de < 2,0%.
3. **Teste de Fumaça na GPU RTX 5060**:
   - O treinamento em lote real sobre 200 obras de treino com sequências de 512 tokens consumiu apenas **1.966,7 MB de VRAM** (menos de 25% da memória de 8 GB da GPU), com redução consistente da perda (0,5113 $\to$ 0,0594) em **19,17 segundos**.

---

## 2. Auditoria e Telemetria de Parâmetros

A tabela a seguir apresenta a auditoria quantitativa da rede neural configurada:

| Componente | Parâmetros | Proporção | Estado |
| :--- | ---: | :---: | :---: |
| **Backbone Transformer Base (BERTimbau)** | 108.924.674 | 99,46% | Congelado |
| **Adaptadores LoRA (`query`, `value`, r=16, $\alpha$=32)** | 589.824 | 0,538% | Treinável |
| **Cabeça de Classificação Linear (768 $\to$ 2)** | 1.538 | 0,002% | Treinável |
| **Total Global** | **109.516.036** | **100,00%** | |
| **Total Treinável** | **591.362** | **0,54%** | **Atende ao teto de < 2%** |

---

## 3. Telemetria do Teste de Fumaça na GPU Local (RTX 5060)

O teste de fumaça foi executado pelo script oficial `scripts/smoke_test_bertimbau.py`:

- **Ambiente de Execução**: NVIDIA GeForce RTX 5060 Laptop GPU (8 GB GDDR6)
- **Frameworks**: PyTorch 2.14.0+cu130, Hugging Face Transformers 4.57.6, PEFT 0.21.2
- **Amostras Treinadas**: 200 obras com evidências textuais do lote congelado `evidencias_rag_dev.jsonl`
- **Tamanho do Lote (Batch Size)**: 8 sequências de até 512 tokens
- **Otimizador**: AdamW ($\text{lr} = 2 \times 10^{-4}$) com Precisão Mista (AMP `autocast('cuda')`)

### Resultados de Desempenho e Eficiência:
- **Tempo de Execução (1 época)**: **19,17 segundos** (teto máximo tolerado: 10 minutos).
- **VRAM Pico Alocada**: **1.966,7 MB** (margem de segurança de mais de 6 GB livres na RTX 5060).
- **Evolução da Perda Ponderada**:
  - Passo 5: 0,3296
  - Passo 10: 0,1748
  - Passo 15: 0,0551
  - Passo 25 (Final): **0,0594** (redução líquida de +0,4519).

---

## 4. Decisão Formal de Arquitetura e Protocolo de Dados

Conforme deliberado no planejamento da Sprint 7 e respaldado pelos relatórios das Features 018 e 019:

1. **BERTimbau como Detector Binário de Risco (Classe 0: Regular vs. Classe 1: Em Risco)**:
   - A formulação binária é formalmente consolidada para as obras que contam com suporte documental.
   - O modelo de linguagem atua na detecção de indícios de risco contratual, técnico ou orçamentário.
   - A atribuição causal fina em 4 classes permanece sob o classificador tabular hierárquico (LightGBM), onde demonstrou alta eficácia sem depender de textos inexistentes.
2. **Confirmação do Ramo A (Suficiência de 2025)**:
   - Com o rebaseline da Feature 018 comprovando ganho do texto autêntico (C2 superando C1 em Balanced Accuracy no teste retido: 67,05% vs 66,00%) e o motor RAG da Feature 019 materializado com 100% de estabilidade, **o projeto segue pelo Ramo A**.
   - A coleta de 2024 permanece registrada na documentação como protocolo de contingência e discussão metodológica para o texto final da dissertação.

---

## 5. Prontidão Técnica para a Sprint 8

Com a conclusão da Feature 020, o projeto atinge **prontidão técnica integral** para a Sprint 8:
- O pipeline de dados está livre de vazamento (Feature 018).
- As evidências textuais estão indexadas e materializadas de forma congelada (Feature 019).
- A arquitetura BERTimbau + LoRA está configurada, validada e auditada com consumo leve na GPU local (Feature 020).
