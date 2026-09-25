# Onde Random Forest se encaixa no TCC

Investigação em 2026-09-19. A interpretação abaixo é uma proposta metodológica;
não há registro suficiente para afirmar qual uso o professor pretendia.

## Papel de cada componente

| Componente | Entrada | Saída | Etapa |
|---|---|---|---|
| GTE multilingual | Texto canônico do chunk | Vetor denso de 768 números | Sprint 4 |
| PostgreSQL/pgvector | Vetor de consulta e filtros | Chunks próximos, documentos e proveniência | Sprint 4 |
| RandomForestClassifier | Atributos numéricos/categóricos preparados + rótulos homologados no treino | Classe de risco e probabilidades estimadas | Experimento supervisionado posterior |

Random Forest combina árvores de decisão. Pode funcionar como baseline de classificação
com atributos tabulares, e também pode receber embeddings como atributos numéricos.
Não é necessário para produzir embeddings GTE nem para consultar pgvector.
Documentação: [RandomForestClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html).

## Proposta de comparação para este projeto

1. Baseline trivial (`DummyClassifier`) para medir o ganho sobre a classe majoritária.
2. Random Forest com atributos tabulares disponíveis na data de corte.
3. Regressão logística com embeddings agregados por obra/data-base.
4. Random Forest com os mesmos embeddings; opcionalmente atributos tabulares + texto.

Esta é uma proposta experimental, não uma afirmação de superioridade do Random Forest.
Comparar macro-F1, balanced accuracy, recall por classe e matriz de confusão usando
as mesmas partições. Registrar semente, parâmetros e versões; ajustar hiperparâmetros
somente no treino/validação, preservando teste final. Probabilidades precisam de avaliação
de calibração antes de serem interpretadas como probabilidade operacional de risco.

## Condições necessárias antes de treinar

- Homologar as classes da constituição: 0 regular; 1 deficiência técnica;
  2 deficiência orçamentário-financeira; 3 abandono/falhas da contratada.
  Ausência de evidência continua NULL/PENDENTE. Relevância de busca não é classe de risco.
- Definir se o objetivo é classificação retrospectiva da causa ou previsão de um evento
  futuro. Previsão exige horizonte, data de observação e exclusão de informação posterior
  ao evento. A classificação de documentos que já descrevem a paralisação não demonstra
  antecipação de risco.
- Construir uma observação por obra/data-base. Agregar chunks primeiro por documento
  e depois por obra, com política explícita de pesos e deduplicação; não multiplicar
  medidas financeiras pela ponte N:N. Obras sem documentos precisam de tratamento explícito.
- Separar treino/teste por identidade estável da obra, inclusive entre anos e bases.
  Examinar documentos e chunks compartilhados entre obras para impedir vazamento textual.
  `StratifiedGroupKFold` ajuda a manter grupos separados e a preservar as proporções
  das classes quando possível; o grupo precisa refletir essas dependências.
  [Documentação](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html).
- Auditar disponibilidade temporal de cada atributo; fichas sintéticas e campos que
  revelam diretamente o alvo não entram automaticamente. Dados de 2026 continuam
  fora da evidência histórica até 2025, mesmo quando vetorizados.

## Decisão atual

Preparar a recuperação de evidências e o protocolo de avaliação na Sprint 4. Não treinar
Random Forest enquanto os rótulos estiverem pendentes. A pergunta a esclarecer com o
professor é se ele propõe Random Forest como baseline tabular, sobre embeddings ou
combinando ambos, e qual é o alvo/horizonte pretendido.
