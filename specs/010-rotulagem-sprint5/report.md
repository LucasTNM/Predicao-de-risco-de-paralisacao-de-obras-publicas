> Atualização posterior: a feature [011](../011-situacao-causa-risco/plan.md) autoriza classe 0 pela situação sem contradições e adiciona recuperação de causas ausentes. Este documento preserva a etapa v1.

# Sprint 5 — plano completo e primeira entrega de rotulagem

**Data:** 2026-09-28
**Estado:** infraestrutura implementada e primeiro lote aplicado; rotulagem científica ainda parcial.
**Branch:** `codex/sprint5-rotulagem`.

## Plano da sprint
Escopo completo definido antes da implementação: protocolo PCC/ADR, inventário, regras conservadoras, revisão das quatro classes, persistência transacional, invalidação de rótulos obsoletos, auditoria, testes e documentação. Ver [plano](plan.md), [tarefas](tasks.md), [protocolo](protocolo-rotulagem.md) e [guia](quickstart.md).

O PCC §3.2 (página impressa 27, PDF 28) define os códigos; §2.4.2 (impressa 16, PDF 17) explica as causas. O mapeamento dos textos brutos é uma operacionalização conservadora, explicitada no protocolo, não tabela literal do PCC. Não alteramos ADRs nem o objetivo preditivo final; esta entrega trata causas históricas observadas.

## Resultado real no PostgreSQL

| Classe/estado de 2025 | Antes | Depois |
| --- | ---: | ---: |
| 0 — regular / sem risco evidenciado | 0 | 0 |
| 1 — deficiência técnica | 0 | 978 |
| 2 — deficiência orçamentário-financeira | 0 | 104 |
| 3 — abandono da contratada | 0 | 423 |
| NULL — pendente | 28.288 | 26.783 |
| Total | 28.288 | 28.288 |

1.505 rótulos por regras (5,32% das observações de 2025); zero revisões humanas importadas. Todas as 32.292 observações de 2026 permanecem NULL. ROTULADO registra preenchimento técnico, sem alegar homologação humana.

A reexecução integral reutilizou os 1.505 rótulos e fez **zero atualizações**. As cinco tabelas mantiveram fingerprints idênticos excluindo exclusivamente label_risco, origem_rotulo, status_rotulagem e updated_at da fato. O fingerprint de dim_embedding inclui o vetor, texto, tokens e metadados.

## Pendências de 2025

| Motivo | Quantidade |
| --- | ---: |
| Causa ausente/não informada; regularidade exige revisão | 23.586 |
| Causa não mapeada/ambígua | 3.165 |
| Situação nominal em conflito com causa | 16 |
| Causas múltiplas/texto livre | 16 |
| Total | 26.783 |

Os 23.586 incluem 23.526 NULL mais valores vazios equivalentes como hífen/não informado. Não foram convertidos em classe 0. Rescisão genérica, dificuldade financeira/técnica da executora, execução defeituosa e motivos administrativos exigem contexto. Isso evita inventar uma hierarquia entre classes sobrepostas.

## Entregas técnicas

- Catálogo de 13 regras exatas com versão/hash, original preservado e corte 2025.
- CLI para inventariar, simular/aplicar, importar revisão e auditar; saídas JSON UTF-8 atômicas sem sobrescrita.
- Fila completa de 2025 com id_fato, contexto, snapshot e razão de pendência.
- Revisão 0–3 com revisor declarado, justificativa, arquivo original/transcrição fiel UTF-8, hash, data e trecho literal; zero exige declaração de regularidade.
- Lote transacional: locks, revalidação, rollback, reuso e rejeição de decisão divergente.
- Reload invalida rótulo se a fonte mudar, inclusive situação/pacto; carga idêntica preserva decisão.
- Auditoria de rótulos verifica fonte/snapshot/método e continua compatível com modo estrito de ausência de labels (`allow_labels=False`).
- Sem migração do esquema, novas dependências ou alteração de embeddings.

## Testes
158 testes aprovados em 8,22 s, incluindo PostgreSQL descartável. Cobertura: quatro classes via revisão, causas negativas/ambíguas, datas, SHA/trecho, fonte modificada, simulação sem escrita, rollback por falha no segundo UPDATE, concorrência, duplicidade, idempotência, reload, saída atômica e caminhos relativos. Falhas iniciais esperadas demonstraram ausência do módulo e os defeitos de invalidação/validação anteriores, corrigidos antes da operação.

## Limitações e próxima etapa
A infraestrutura não autentica a identidade do revisor nem verifica independentemente a autenticidade de sua fonte; confere a declaração, conteúdo e integridade. Revisão humana não foi fabricada. A primeira entrega não contém contraste de classe 0 e **não está homologada para treinamento**.

Próximo trabalho da sprint: revisar evidências de regularidade e ambiguidades, começando pelos casos raros e conflitos; produzir decisões conforme quickstart. Homologar o protocolo/amostra e a origem documental; manter abertas as pendências T011/T013/T014 da feature 007. Treinamento, pesos, partições e comparação com Random Forest permanecem fora desta entrega. Nenhuma métrica preditiva foi medida.

## Evidências locais
- logs/sprint5_inventario_inicial.json e logs/sprint5_inventario_final.json — todas as observações e fila.
- logs/sprint5_simulacao.json — 1.505 propostas e zero updates.
- logs/sprint5_aplicacao.json — decisões/proveniência e fingerprints antes/depois.
- logs/sprint5_retomada.json — 1.505 reusos, zero updates e preservação.
- logs/sprint5_auditoria.json — proveniência/distribuição e fingerprints finais.
- logs/sprint5_integridade_final.json — verificação estrutural/textual/vetorial e de rótulos.
- logs/sprint5_regressao.txt — testes; logs/sprint5_regressao_inicial.txt — falhas anteriores às correções.

Logs, corpus e documentos locais continuam ignorados pelo Git. spec/plan/tasks/research/protocolo/contratos/guia/relatórios em specs são versionáveis.


## Verificação final
Auditoria independente ao final: zero inconsistências estruturais, textuais, vetoriais e de proveniência. Comparação exata das 1.505 proveniências no banco com o relatório de aplicação confirmou que a retomada não as alterou. SpecKit converge sem lacunas técnicas; 16/16 tarefas de implementação concluídas, preservadas as pendências científicas descritas acima. Branch local sem commit/push nesta execução.
