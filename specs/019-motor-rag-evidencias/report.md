# Relatório Técnico: Motor de Busca RAG por Obra (Sprint 7)

**Feature**: `019-motor-rag-evidencias`  
**Data de Conclusão**: 2026-10-19  
**Status**: Concluído e Auditado com Sucesso  

---

## 1. Resumo Executivo

A Feature 019 implementou com sucesso o **Motor de Busca RAG Restrito por Obra** no PostgreSQL/pgvector, cumprindo o card do Trello *"Desenvolvimento do Motor de Busca RAG"* sob estrita conformidade constitucional:

1. **Restrição Inviolável por Obra**: A recuperação opera exclusivamente sobre os chunks vinculados à própria obra consultada através da relação dimensional `tcc.ponte_documento_embedding` $\to$ `tcc.dim_documento`.
2. **Expurgo de Vazamento**: Todas as fichas sintéticas foram formalmente excluídas da recuperação (`origem_documento != 'ficha_sintetica'`). Apenas documentos autênticos (PDFs de editais, termos e relatórios de fiscalização) são elegíveis.
3. **Consultas Causais Auditadas**: As 4 consultas causais (Regular, Técnica, Orçamentária e Abandono) foram formuladas e auditadas sem nenhum termo de situação da obra ("paralisada", "em execução"), eliminando qualquer indução ao alvo (*Artigo I da Constituição*).
4. **Lotes Congelados Materializados**: Os lotes de evidências foram materializados em formato imutável (`jsonl`) para as partições de treino/dev (14.522 obras) e teste retido (3.632 obras) com manifestos auditáveis e hashes SHA-256.

---

## 2. Lotes Materializados e Hashes SHA-256

Os artefatos congelados foram gerados em `dados_processados/sprint7/` com os seguintes parâmetros:
- Modelo de Embedding: `Alibaba-NLP/gte-multilingual-base` (Sprint 4, 768 dimensões)
- Métrica de Similaridade: Distância Cosseno Exata (`<=>`)
- Top-$k$: até 4 fragmentos deduplicados por obra

| Partição | Arquivo | Total Obras | Obras c/ Texto | Chunks Totais | Hash SHA-256 |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Treino/Dev** | `evidencias_rag_dev.jsonl` | 14.522 | 324 (2,23%) | 1.158 | `af3b86940a04da6e06fc454226f345851d953046f494c2562489e246cf37d7a5` |
| **Teste Retido** | `evidencias_rag_teste.jsonl` | 3.632 | 98 (2,70%) | 359 | `b680ee11cb759600e163c46a6f0590a2be2d5ebfe5f1f3a38891d4e7d0d0f28a` |

---

## 3. Cobertura Textual por Classe com Documentos Autênticos

A tabela a seguir apresenta a distribuição real de textos autênticos por classe após o expurgo das fichas sintéticas:

| Partição | Classe | Significado | Total Obras | Obras com Texto | Cobertura Textual |
| :--- | :---: | :--- | :---: | :---: | :---: |
| **Treino/Dev** | **0** | Regular (Execução / Concluída) | 13.319 | 313 | **2,35%** |
| | **1** | Deficiência Técnica | 782 | 10 | **1,28%** |
| | **2** | Deficiência Orçamentário-Financeira | 83 | 1 | **1,20%** |
| | **3** | Abandono / Falhas da Contratada | 338 | 0 | **0,00%** |
| **Teste Retido** | **0** | Regular (Execução / Concluída) | 3.330 | 97 | **2,91%** |
| | **1** | Deficiência Técnica | 196 | 1 | **0,51%** |
| | **2** | Deficiência Orçamentário-Financeira | 21 | 0 | **0,00%** |
| | **3** | Abandono / Falhas da Contratada | 85 | 0 | **0,00%** |

---

## 4. Diagnóstico de Suficiência para o BERTimbau (Feature 020)

### 4.1 Impossibilidade Empírica de BERTimbau Causal de 4 Classes
- No universo de 2025 sem fichas sintéticas, existem apenas **12 obras paralisadas com textos autênticos** em toda a base (11 da Classe 1, 1 da Classe 2 e **0 da Classe 3**).
- Consequentemente, é cientificamente inviável treinar um modelo de linguagem para atribuição causal fina entre as classes 1, 2 e 3 com o corpus autêntico de 2025, pois as classes 2 e 3 simplesmente não possuem texto.

### 4.2 Decisão de Arquitetura Textual
- O modelo **BERTimbau + LoRA (Feature 020)** deve operar estritamente como **Detector Binário de Risco (Classe 0: Regular vs. Classe 1: Em Risco)** nas obras que possuem texto.
- A tarefa de **atribuição causal fina (separação das causas 1, 2 e 3)** permanece sob a responsabilidade do modelo tabular hierárquico (LightGBM), que provou no teste retido atingir até 95,41% de sensibilidade na classe 1 e 84,71% na classe 3 com base em dados cadastrais, financeiros e temporais.

### 4.3 Protocolo de Contingência para 2024
A mineração de dados de 2024 permanece como contingência condicionada aos seguintes critérios:
1. Somente obras paralisadas com `id_tcu` inédito em relação a 2025.
2. Apenas documentos originais autênticos (vedada geração de fichas sintéticas).
3. Se o total de novos PDFs densos autênticos for $\ge 300$, executa-se a ingestão de 2024. Se for inferior, adota-se a Opção C do TCC (experimento comparativo documentado, evidenciando o gap estrutural de digitalização nos órgãos públicos).

---

## 5. Auditoria da Amostra de 30 Obras (SC-005)

Foi inspecionada uma amostra estratificada de 30 obras (15 com texto e 15 sem texto):
- **Obras sem texto**: Todas retornaram `sem_evidencia_textual = True`, com `total_chunks_recuperados = 0` e `chunks = []`. Nenhuma obra recebeu fragmentos indevidos.
- **Obras com texto**: Todos os chunks recuperados continham texto nativo autêntico, similaridade cosseno entre 0,65 e 0,82, com identificação precisa do documento de origem e indicação da consulta causal mais próxima (`regular`, `tecnica` ou `abandono`).

---

## 6. Conformidade com Critérios de Sucesso

- **SC-001**: 100% dos fragmentos pertencem à própria obra consultada e a fontes autênticas permitidas. [Concluído]
- **SC-002**: Lotes de 18.154 obras materializados em 26,7 segundos (meta: < 30 min). [Concluído]
- **SC-003**: Execução determinística com hash idêntico. [Concluído]
- **SC-004**: Relatório de cobertura por classe documentado. [Concluído]
- **SC-005**: Amostra de 30 obras inspecionada e auditada. [Concluído]
