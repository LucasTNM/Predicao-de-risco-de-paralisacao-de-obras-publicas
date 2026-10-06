# Implementation Plan — Situação e causa
**Branch Git**: codex/sprint5-rotulagem | **Feature**: 011-situacao-causa-risco | **Date**: 2026-09-28
## Summary
Estender sprint 5 com classe 0 pela situação autorizada e pacote de recuperação de causa ausente. Preservar política v1 imutável para auditoria dos 1.505 rótulos existentes; criar v2 e aceitar versões conhecidas.
## Technical Context
Python 3.14, psycopg, pytest e biblioteca padrão existentes. PostgreSQL Docker e arquivos JSON UTF-8; nenhuma migração/dependência nova. 28.288 fatos históricos. Recuperação faz consultas em lote de vínculos/chunks apenas das obras pertinentes; sem modelo de embeddings, treino ou scraping nesta fase.
## Constitution Check
Princípio I emendado para 2.0.0 via speckit-constitution: mudança incompatível da regra de zero autorizada pelo usuário. II/III/IV preservados: nenhum texto ou esquema alterado; v1 congelada e evidências atômicas.
## Project Structure
src/labeling/policy_v2.py (classificação e auditoria multiversão); src/database/labeling.py (compatibilidade e método de origem); src/labeling/recovery.py (pacotes/trechos); scripts/rotular_sprint5.py (comando recuperar); tests/test_labeling_v2.py e testes de integração existentes.
## Execution
1. Especificação e emenda; 2. testes; 3. v2 e reuso multiversão; 4. recuperação em lote; 5. regressão real; 6. simulação/aplicação/reexecução/recuperação, auditoria e documentação; 7. converge.
## Decisions
Regra R00 só quando causa é vazia/Não informado/hífen. Origem com pendência, paralisação, cancelamento, rescisão, inacabamento ou reinício bloqueia zero. Regra histórica é referência tabular, não comprovação por laudo. Fallback exige conferir identidade da obra, cronologia e causa; expressões no texto servem apenas para localizar trechos. Relatórios de recuperação não têm label sugerida por palavra-chave.
## Risks
Maioria dos vínculos de causa NULL são fichas sintéticas. Os documentos não confirmados podem nem pertencer à obra (amostra DNIT contém evento e serviço de monitoramento). Recoletar fonte original quando necessário. Nunca propagar rótulos por proximidade vetorial. Sem evidência adequada permanece pendente, com tarefa de coleta explícita.

## Avaliação das pendências — 2026-09-29

A avaliação com SpecKit separou as 9.964 paralisadas pendentes em 3.181 com causa presente não resolvida e 6.783 sem causa utilizável. Após ativação do Docker, consulta somente leitura confirmou os totais, a distribuição documental por base e a validade dos rótulos existentes; nenhum registro de 2026 está rotulado. Nenhum rótulo ou código foi alterado nesta avaliação.

Recomenda-se revisar o catálogo das causas presentes e, para causas ausentes, conferir a identidade dos vínculos PNCP antes de um piloto de recuperação histórica: 22 obras DNIT com documentos não confirmados mais 60 casos novos distribuídos entre as bases, com maior participação de SISMOB/SIMEC. Ausência de evidência mantém `label_risco = NULL`; cancelamento, ficha sintética e similaridade textual não comprovam causa.

A feature 011 permanece entregue no escopo técnico original. O piloto, correções dos coletores e revisão científica são trabalho futuro proposto, ainda não executado, a detalhar em nova spec/plan/tasks antes da implementação. Consulte a [avaliação e critérios de decisão](avaliacao-pendencias-20260929.md), o [roadmap de recuperação](roadmap-recuperacao.md) e a [análise de consistência SpecKit](analise-speckit-20260929.md).
