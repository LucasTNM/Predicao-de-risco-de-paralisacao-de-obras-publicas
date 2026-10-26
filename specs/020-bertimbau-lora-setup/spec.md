# Feature Specification: 020-bertimbau-lora-setup

**Feature Branch**: `020-bertimbau-lora-setup`

**Created**: 2026-10-19

**Status**: Draft (depende das Features 018 e 019)

**Input**: Cards Trello "Setup do Modelo (BERTimbau + LoRA)" e "Balanceamento de Classes (Tratamento da Assimetria)" — configurar BERTimbau com cabeça de classificação de sequências, integrar PEFT/LoRA congelando a rede base e aplicar pesos de classe na função de perda.

## Ponto de partida

- Pesos de classe já calculados e testados em `src/modeling/loader.py::compute_class_weights` (fórmula N / (K · N_c)), usados no LightGBM e no hierárquico. Para o `treino_dev` (14.522 obras): classe 0 = 0,2726; classe 1 = 4,6426; classe 2 = 43,7410; classe 3 = 10,7411. Estágio 1 binário: `scale_pos_weight` = 11,07.
- Chunks já tokenizados com BERTimbau cased e revisão fixa (450 tokens + 50 de sobreposição).
- Ambiente GPU (`torch 2.14 + cu130`, `transformers 4.57.6`) existe; `peft` ainda não está instalado.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Modelo treinável com poucos parâmetros (Priority: P1)

Como pesquisador, quero carregar o BERTimbau com revisão fixa, adicionar uma cabeça
de classificação e adaptadores LoRA, mantendo os pesos originais congelados, para
treinar na GPU local de 8 GB.

**Why this priority**: Atende ao objetivo do projeto de pesquisa e é pré-requisito do treinamento (Feature 021).

**Independent Test**: Relatório de parâmetros mostra que menos de 2% são treináveis e um passo de treino em lote sintético reduz a perda sem erro de memória.

**Acceptance Scenarios**:

1. **Given** o modelo configurado, **When** os parâmetros forem contados, **Then** apenas adaptadores LoRA e a cabeça de classificação são treináveis.
2. **Given** um lote com 512 tokens, **When** for executado um passo de treino, **Then** o uso de memória fica abaixo do limite da GPU.

---

### User Story 2 - Perda ponderada pela assimetria (Priority: P1)

Como pesquisador, quero que a função de perda receba os pesos de classe calculados
apenas no treino de cada dobra, para penalizar erros nas classes minoritárias.

**Independent Test**: Teste unitário compara os pesos usados na perda com `compute_class_weights` para o mesmo vetor de rótulos.

**Acceptance Scenarios**:

1. **Given** os rótulos de uma dobra de treino, **When** a perda for criada, **Then** os pesos coincidem com a fórmula N / (K · N_c) dessa dobra.
2. **Given** a formulação hierárquica, **When** o Estágio 2 for treinado, **Then** os pesos são recalculados sobre as obras em risco.

---

### User Story 3 - Formulação da Tarefa Textual: Detector Binário e Protocolo 2024 (Priority: P1)

Como pesquisador, quero que o BERTimbau opere como **Detector Binário de Risco (Classe 0: Regular vs. Classe 1: Em Risco / Paralisada)** sobre as obras com evidência textual permitida, integrando-se ao sistema hierárquico em cascata, com protocolo de decisão pré-definido para suficiência de material textual:

1. **Formulação Binária (Acordada)**:
   - O BERTimbau foca na detecção de risco textual (separando obras Regulares de Obras em Risco que englobam classes causais 1, 2 e 3).
   - Suporte amostral em 2025 com fichas mascaradas: ~6.478 regulares e 515 em risco com representação textual.
   - O Estágio 2 (atribuição causal específica entre classes 1, 2 e 3) permanece sob responsabilidade do modelo tabular hierárquico (LightGBM), onde os dados cadastrais/financeiros demonstraram alta eficácia.

2. **Árvore de Decisão sobre Materiais Textuais (Contingência 2024)**:
   - **Cenário 1 — Material de 2025 Suficiente (Caminho Padrão)**: Se a Feature 018 demonstrar que as fichas mascaradas + documentos autênticos de 2025 retêm sinal preditivo sem vazamento, avança-se diretamente para o RAG (Feature 019) e treino do BERTimbau binário sem necessidade de carregar 2024.
   - **Cenário 2 — Material de 2025 Insuficiente (Gatilho da Contingência 2024)**: Se a Feature 018 apontar ausência de sinal textual útil em 2025, avalia-se a inclusão de 2024 sob o seguinte filtro de viabilidade:
     - *Filtro de Não-Sobreposição*: selecionar da base de 2024 (28.242 obras) exclusivamente obras paralisadas cujo `id_tcu` não esteja presente em 2025 (garantindo novos grupos independentes).
     - *Filtro de Documentos Autênticos*: minerar estritamente PDFs densos originais (ex.: DNIT e contratos com arquivos reais no Transferegov), proibindo a geração de fichas sintéticas que apenas reproduzam dados tabulares.
     - *Critério de Corte*: caso a triagem encontre $\ge 300$ novos documentos autênticos de obras paralisadas não sobrepostas, executa-se o pipeline de 2024; caso contrário, adota-se a **Opção C** (experimento comparativo negativo documentado com rigor metodológico no TCC).

**Independent Test**: A decisão entre Cenário 1 e Cenário 2/Opção C fica formalmente registrada em `research.md` a partir das evidências empíricas da Feature 018.

### Edge Cases

- Obra com vários fragmentos: agregação dos logits por obra (média; máximo como variante registrada).
- Obras sem texto: não passam pelo BERTimbau; recebem a predição da referência tabular.
- Incompatibilidade de `peft` com Python 3.14: criar ambiente dedicado fixado, sem alterar ambientes anteriores.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O modelo base DEVE ser BERTimbau cased com revisão fixa, igual ao tokenizer do chunking.
- **FR-002**: Os pesos originais DEVEM permanecer congelados; somente LoRA e cabeça de classificação são treináveis.
- **FR-003**: Hiperparâmetros LoRA (posto, alfa, dropout, módulos-alvo) DEVEM ser configuráveis e registrados.
- **FR-004**: A perda DEVE aceitar pesos de classe calculados por dobra a partir do treino.
- **FR-005**: A entrada DEVE ser o lote de evidências congelado da Feature 019, com no máximo 512 tokens por sequência.
- **FR-006**: Semente, versões e configuração DEVEM ser registradas em manifesto.
- **FR-007**: As dependências novas DEVEM ficar em um arquivo de requisitos próprio da Sprint 7/8.

### Key Entities

- **Configuração do Classificador**: modelo base, revisão, número de classes, parâmetros LoRA, pesos de classe.
- **Política de Agregação**: regra que transforma predições de fragmentos em predição por obra.

## Success Criteria *(mandatory)*

- **SC-001**: Menos de 2% dos parâmetros treináveis.
- **SC-002**: Um epoch de teste de fumaça em 200 obras termina em menos de 10 min na GPU local.
- **SC-003**: Pesos de classe da perda idênticos aos de referência em 100% dos testes.
- **SC-004**: Decisão A/B/C registrada antes do treino completo.

## Assumptions

- O cálculo de pesos de classe já existente é reutilizado; o card de balanceamento se reduz à ligação com a perda.
- A GPU RTX 5060 (8 GB) comporta BERTimbau-base com LoRA em precisão mista e lote pequeno com acumulação de gradiente.
