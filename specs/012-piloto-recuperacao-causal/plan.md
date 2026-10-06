# Implementation Plan: Piloto de recuperação causal
**Branch**: checkout existente | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)
## Summary
Corrigir associação PNCP, auditar 22 legados, selecionar/coletar 60 casos, revisar candidatos e produzir decisão de escala/dataset de acompanhamento.
## Technical Context
Python3.14; requests, psycopg, pytest existentes. PostgreSQL Docker somente leitura; JSON e respostas em logs/piloto_recuperacao/ ignorados. Windows. CLI com persistência atômica e retomada; rede limitada, timeout e tamanho máximo por resposta; até duas rotas por caso. Sem mudança DDL/vetores/políticas v1/v2.
## Constitution Check
I: identidade e data-base exigidas; nenhuma inferência causal sintética. II: respostas completas preservadas e hashes; quarentena lógica sem apagar originais. III: uma linha por fato; sem escrita de corpus. IV: seed42, cache validado por hash, publicação atômica, testes. Gates pré/pós-design aprovados.
## Project Structure
- src/extractors/pncp_identity.py: identificador oficial, validação e rota única.
- src/main.py e src/extractors/pncp.py: remover suposição de sequência e aplicar guardas.
- src/labeling/pilot.py: seleção, auditoria, métricas, reserva por identidade.
- src/labeling/pilot_sources.py: respostas oficiais, cache, adapters e classificação dos resultados de busca.
- scripts/piloto_recuperacao.py: preparar, coletar, relatar.
- tests/test_recovery_pilot.py e tests/test_pncp_identity.py: regressão e falhas.
- logs/piloto_recuperacao/: população, manifesto, respostas, resultados e reserva.
## Execution
Pesquisa delegada de rotas oficiais pelo speckit-plan; contratos primeiro, testes antes da implementação, consultas somente leitura. Manter decisões científicas abertas quando não existir evidência suficiente. Quarentena é registro auxiliar aplicado ao piloto; alteração dos vínculos existentes exigiria migração separada.
