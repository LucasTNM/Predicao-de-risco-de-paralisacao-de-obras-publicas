# Validação parcial da Sprint 4 — atualizada em 2026-09-19

> Continuação mais recente: [evaluation.md](evaluation.md). T012 concluída com
> benchmark ponderado e espaço do volume/host; 74 testes aprovados. Revisão assistida
> dos pacotes concluída com métricas exploratórias, sem homologação humana de T011.
> Nenhum vetor novo nessa continuação: banco permanece com 125 vetores.

## Gate de comprimento

`scripts/auditar_tokens_sprint4.py` leu o banco em transação somente leitura e auditou 185.789/185.789 fragmentos únicos, sem truncamento. Relatórios operacionais:

| Candidato | Revisão | Janela | Excedentes | Máximo |
|---|---|---:|---:|---:|
| multilingual-e5-base | `d128750597153bb5987e10b1c3493a34e5a4502a` | 512 | 249 | 4.582 |
| gte-multilingual-base | `9bbca17d9273fd0d03d5725c7a4b0f6b45142062` | 8.192 | 0 | 4.580 |

Os relatórios são `logs/sprint4_tokens_e5_20260916_182914_565629.json` e `logs/sprint4_tokens_gte_20260916_183039_953697.json`. Ambos observaram o mesmo conjunto de identidades. E5 foi reprovado para carga integral; GTE passou apenas no gate de comprimento.

## Modelo, ambiente e código externo

GTE usa revisão de modelo `9bbca17d9273fd0d03d5725c7a4b0f6b45142062` e código de `Alibaba-NLP/new-impl` na revisão `40ced75c3017eb27626c9d4ea981bde21a2662f4`. Foi feita inspeção estática dos imports e procura por chamadas de execução, subprocesso e rede nos arquivos `configuration.py` e `modeling.py` dessa revisão; nenhuma dessas chamadas foi encontrada. A execução foi limitada ao ambiente isolado `.venv-sprint4`, com versões fixadas em `requirements-sprint4.txt`; `torch.cuda.is_available()` retornou `False`, logo a medição é de CPU.

## Piloto técnico

- Inferência em leitura: `logs/sprint4_piloto_20260916_184036_176507.json`; 17 vetores de 768 dimensões, finitos e com norma ~1, sem escrita no banco; inferência em 4,336 s.
- Persistência: `logs/sprint4_piloto_20260916_184210_972239.json`; 17 vetores gravados com modelo/revisão, 4,405 s de inferência; banco válido.
- Reexecução: `logs/sprint4_piloto_20260916_184347_645751.json`; os mesmos 17 foram `reutilizado`, contagem de vetores permaneceu 17.
- Regressão após código e dados: 58 testes aprovados; `python -m src.main --modo validar-banco` retornou `valido: true` e zero em dez verificações.

## Gate ainda aberto

Não há avaliação de recuperação revisada manualmente nem projeção confiável de vazão/armazenamento para todos os 185.789 vetores. A carga vetorial integral e o índice HNSW não foram iniciados. Rótulos continuam nulos; os vetores não mudam a destinação das 225 ocorrências de 2026.

## Continuação: implementação e execução em 2026-09-19

Último commit conferido: `ea2b5ab`. Alterações locais anteriores da Sprint 4 foram
preservadas e ampliadas. Checklist de requisitos: 6/6. Sem extension hooks configurados.

### Implementação

- Contrato compartilhado de GTE, com revisão de pesos e código fixadas, mesma
  normalização para documentos/consultas e rejeição de entrada acima da janela.
- Busca cosseno **exata** no PostgreSQL (`<=>`), com candidatos materializados;
  ano/origem e modelo/revisão filtrados antes do top-k. Chunks únicos e ocorrências
  com documento, fato, posição e offsets. Nenhum índice ANN criado.
- CLI de avaliação, relatório de tempo/espaço e pacote local com textos para revisão;
  métricas condicionadas a julgamentos do mesmo universo e das mesmas consultas.
- Piloto ampliável a 1..16 chunks por estrato, mantendo padrão anterior de 1.
- Auditoria integral continua cobrindo todos os conteúdos e vínculos; cursores
  agora buscam 2.048 linhas por viagem, em vez do padrão 100.

### Testes

- `.venv/Scripts/python.exe scripts/testar_sprint3.py`: **69 passed in 11.79s**,
  incluindo PostgreSQL real descartável, após a última alteração de código.
- `.venv-sprint4/Scripts/python.exe -m pytest tests/test_sprint4.py -q`: **9 passed**.
- `pip check` do ambiente de inferência: sem dependências quebradas.
- A tentativa inicial de rodar a suíte completa na `.venv-sprint4` falhou na coleta
  por ausência de fpdf/openpyxl/pandas. A suíte completa foi então executada no
  ambiente correto `.venv`; não se trata de regressão funcional.

Cobertura nova: dimensão/finitude/norma, fronteira 8.192/8.193 tokens sem truncamento,
texto vazio, métricas conhecidas, corpus de revisão divergente/revisão pendente,
ranking cosseno real, filtros de ano/origem/revisão, proveniência e deduplicação da amostra.

### Piloto ampliado e custo

Relatório: `logs/sprint4_piloto_20260919_155659_543849.json`.

| Medida | Resultado |
|---|---:|
| Amostra (8 por ano/base/origem + borda, deduplicada) | 125 chunks |
| Vetores anteriores / novos / finais | 17 / 108 / 125 |
| Tokenização + inferência em CPU, batch 2 | 33,385 s |
| Vazão dessa amostra | 3,744 chunks/s |
| RSS após inferência | 1.622.433.792 bytes |
| Pico de working set do processo (Windows) | 2.298.302.464 bytes |
| Projeção linear de inferência para 185.789 | 49.621 s (~13,8 h) |
| Valor vetorial teórico integral, sem overhead (3.080 bytes/chunk) | 572.230.120 bytes |
| `pg_column_size` médio observado dos 125 vetores | 3.076 bytes |
| Relação atual completa, índices e TOAST incluídos | 556.179.456 bytes |

Integridade operacional antes/depois: `valido: true`, dez verificações zeradas.
Contagens preservadas: 60.580 obras/fatos, 51.009 documentos, 185.789 chunks e
232.902 vínculos. Rótulos continuam nulos. A projeção **não** inclui escrita, WAL,
índice, inicialização ou auditorias; a amostra não foi ponderada pelo comprimento.
O tamanho atual da relação inclui texto/tokens/índices e não representa o espaço
adicional de uma carga completa. Não foi atestada capacidade livre no volume do servidor.

### Busca operacional

| Recorte | Universo vetorizado | Consultas | Mediana | Máximo |
|---|---:|---:|---:|---:|
| 2025 | 73 | 6 | 35,11 ms | 36,54 ms |
| 2026 | 63 | 6 | 35,03 ms | 40,26 ms |

Há conteúdos compartilhados entre anos; 73 + 63 não é contagem de vetores únicos.
Latências incluem busca e leitura da proveniência; excluem geração do vetor da consulta.
São seis observações locais por recorte, não benchmark de concorrência ou p95 de produção.
`EXPLAIN ANALYZE` da seleção cosseno equivalente: 26,938 ms (2025), 25,821 ms (2026).

Relatórios: `logs/sprint4_busca_20260919_155902_010329.json` e
`logs/sprint4_busca_20260919_155947_188881.json`. Pacotes para revisão:
`logs/sprint4_revisao_20260919_155902_010329.json` e
`logs/sprint4_revisao_20260919_155947_188881.json`.
Status de ambos: `AGUARDANDO_REVISAO_SEMANTICA`. Não foram atribuídos julgamentos
de relevância nem precisão/recall fictícios; similaridade não é probabilidade de risco.

### Decisão e limites

**Manter piloto e busca exata.** Não há evidência de necessidade de HNSW neste tamanho.
A carga integral segue pendente da revisão semântica e de orçamento medido em amostra
representativa dos comprimentos, incluindo espaço livre no servidor. T009 permanece
parcial: infraestrutura e evidência técnica entregues; homologação semântica pendente.
Random Forest foi investigado em [random-forest.md](random-forest.md), como candidato
de classificação supervisionada futura, sem treinamento ou alteração dos rótulos.

Reexecução operacional: `logs/sprint4_piloto_20260919_155934_098423.json`,
125 vetores antes/depois, todos reutilizados, inferência 33,118 s e integridade válida.

Convergência: 6 requisitos funcionais, 4 critérios de sucesso, 4 fases do plano e
4 princípios constitucionais conferidos. Duas lacunas `partial`, severidade HIGH,
rastreáveis a FR-006/SC-004 e ao gate de escala: T011/T012 adicionadas a `tasks.md`.
T010 concluída; T009 continua parcial. Sem hooks antes/depois de implementação/convergência.

## Continuidade e conclusão técnica — 2026-09-23
A [feature 009](../009-conclusao-sprint4/report.md) concluiu a vetorização dos 185.789 chunks elegíveis. Foram preservados os 157 vetores anteriores e gerados 185.632 novos; auditoria integral, 64 recomputações finais em CPU, retomada e busca exata aprovadas. Nenhuma origem/rótulo foi homologada automaticamente. Os registros anteriores deste documento descrevem suas respectivas etapas históricas.
