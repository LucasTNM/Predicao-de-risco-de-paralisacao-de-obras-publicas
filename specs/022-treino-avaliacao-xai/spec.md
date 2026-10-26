# Feature Specification: 021-treino-avaliacao-xai

**Feature Branch**: `021-treino-avaliacao-xai`

**Created**: 2026-10-19

**Status**: Draft (depende da Feature 020)

**Input**: Card Trello "Execução do Treinamento e Avaliação de Desempenho (XAI)" — rodar o ajuste fino supervisionado, avaliar no teste com F1, MCC e curvas PR, e extrair pesos de atenção para explicabilidade.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ajuste fino com validação agrupada (Priority: P1)

Como pesquisador, quero treinar o classificador BERTimbau + LoRA com validação
agrupada por obra no `treino_dev`, escolhendo hiperparâmetros e parada antecipada
apenas pela validação, para obter um modelo final sem tocar no teste.

**Independent Test**: Métricas por dobra registradas; nenhuma obra aparece em treino e validação da mesma dobra.

**Acceptance Scenarios**:

1. **Given** as dobras agrupadas, **When** o treino terminar, **Then** cada dobra tem Macro-F1, MCC e AUC-PR por classe registrados.

---

### User Story 2 - Avaliação comparativa única no teste retido (Priority: P1)

Como autor do TCC, quero comparar o BERTimbau (e o sistema híbrido) com a referência
oficial corrigida da Feature 018 nas mesmas obras de teste, com métricas robustas.

**Independent Test**: Tabela única com Macro-F1, Balanced Accuracy, MCC, recall/precisão por classe, curvas PR por classe e intervalos de confiança por bootstrap.

**Acceptance Scenarios**:

1. **Given** o modelo final, **When** avaliado uma única vez no teste, **Then** as métricas são reportadas para (a) obras com texto e (b) todas as obras via sistema híbrido.
2. **Given** a referência corrigida, **When** comparada, **Then** a diferença é acompanhada de intervalo de confiança e teste pareado.

---

### User Story 3 - Explicabilidade com verificação de fidelidade (Priority: P2)

Como pesquisador, quero explicações por obra (atenção do encoder e uma técnica de
atribuição como gradientes integrados) e, para a referência LightGBM, valores SHAP,
para mostrar quais trechos e atributos sustentam cada predição.

**Why this priority**: Atende ao objetivo de XAI; pesos de atenção isolados não comprovam explicação, por isso exige-se um teste de fidelidade.

**Independent Test**: Teste de deleção: remover os tokens mais atribuídos reduz a confiança da classe prevista mais do que remover tokens aleatórios.

**Acceptance Scenarios**:

1. **Given** 20 obras de teste por classe (ou todas, se houver menos), **When** as explicações forem geradas, **Then** há mapas de atenção, atribuições e resultado do teste de deleção.
2. **Given** as explicações, **When** um token de situação proibido aparecer entre os mais relevantes, **Then** o caso é registrado como alerta de vazamento residual.

### Edge Cases

- Classes com poucos exemplos no teste (classe 2: 21 obras): reportar intervalos de confiança largos; não concluir superioridade sem significância.
- Divergência entre atenção e atribuição: reportar ambas, sem escolher a mais conveniente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Treinamento DEVE usar semente fixa, pesos de classe por dobra e parada antecipada pela validação.
- **FR-002**: O teste retido DEVE ser consultado uma única vez, após o pré-registro do modelo final.
- **FR-003**: Métricas obrigatórias: Macro-F1, Balanced Accuracy, MCC, recall/precisão por classe, curvas PR e AUC-PR por classe, matriz de confusão e IC 95% por bootstrap.
- **FR-004**: XAI DEVE incluir atenção do encoder, uma técnica de atribuição por gradiente e SHAP para a referência LightGBM.
- **FR-005**: XAI DEVE incluir teste de fidelidade (deleção) e verificação de termos proibidos.
- **FR-006**: Modelos, adaptadores e métricas DEVEM ser salvos com manifesto e hash; adaptadores e dados ficam fora do Git.

## Success Criteria *(mandatory)*

- **SC-001**: Tabela comparativa final com todos os modelos nas mesmas 3.632 obras.
- **SC-002**: Curvas PR das 4 classes geradas para a referência e para o BERTimbau.
- **SC-003**: Explicações e teste de deleção para pelo menos 60 obras de teste.
- **SC-004**: Treino completo (5 dobras + modelo final) em menos de 8 h na GPU local.

## Assumptions

- A formulação textual (Opção A/B/C) foi decidida na Feature 020.
- Os resultados serão usados nos capítulos de Resultados e Discussão; um resultado negativo do BERTimbau é aceitável e deve ser reportado.
