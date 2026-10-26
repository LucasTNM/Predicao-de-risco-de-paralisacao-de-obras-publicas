# Checklist de Requisitos: 020-bertimbau-lora-setup

- [ ] Modelo base fixado em BERTimbau cased (`neuralmind/bert-base-portuguese-cased`).
- [ ] Adaptadores LoRA integrados via PEFT congelando os pesos do backbone transformer.
- [ ] Menos de 2% de parâmetros treináveis (< 2,2M sobre ~110M totais).
- [ ] Função de perda no PyTorch penalizando a classe minoritária de risco com pesos idênticos a `compute_class_weights`.
- [ ] Dataset PyTorch lendo fragmentos do lote congelado `evidencias_rag_dev.jsonl` da Feature 019.
- [ ] Sequências truncadas/padded em no máximo 512 tokens.
- [ ] Teste de fumaça executado na GPU local RTX 5060 sem estouro de memória (VRAM < 8 GB).
- [ ] Decisão de arquitetura binária formalizada no relatório.
