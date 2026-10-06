> Atualização posterior: a feature [011](../011-situacao-causa-risco/plan.md) autoriza classe 0 pela situação sem contradições e adiciona recuperação de causas ausentes. Este documento preserva a etapa v1.

# Implementation Plan: Sprint 5 — rotulagem histórica
**Branch Git**: `codex/sprint5-rotulagem` | **Feature SpecKit**: `010-rotulagem-sprint5` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary
Entregar nesta sprint a infraestrutura de rotulagem e aplicar a fração causal inequívoca de 2025. Quatro classes nominais (não níveis de gravidade): 0 regular, 1 técnica, 2 financeira, 3 abandono. Evidência insuficiente fica pendente. Revisão científica não é simulada pelo agente.

## Technical Context
**Language/Version**: Python 3.14.3 do ambiente principal existente.
**Dependencies**: biblioteca padrão, psycopg, python-dotenv, pytest existentes.
**Storage**: PostgreSQL 17/pgvector 0.8.6 no Docker; cinco tabelas atuais; arquivos JSON locais atômicos.
**Testing**: pytest + banco temporário tcc_test_UUID via scripts/testar_sprint3.py.
**Platform/Type**: Windows/PowerShell; pipeline Python/CLI local.
**Performance Goals**: uma leitura por inventário; aplicação em lote com consultas parametrizadas; sem processamento de embeddings.
**Constraints**: sem alteração de DDL, sem atribuições a 2026, sem inferência semântica genérica; transação integral e bloqueio das fontes durante aplicação.
**Scale/Scope**: 60.580 fatos (28.288 de 2025 / 32.292 de 2026), 185.789 vetores; catálogo e revisão, sem treino.

## Constitution Check
Pré e pós-design aprovados: I — corte 2025, NULL != 0 e fichas sintéticas excluídas das evidências revisadas; II — nenhum texto/tokens alterados; III — cinco tabelas e fato por obra/data-base preservados; IV — catálogo/fingerprints, gravação atômica e testes reais. Nenhuma emenda constitucional necessária.

## Project Structure
- `src/labeling/policy.py`: catálogo exato, decisões puras, validação de revisão e fingerprints.
- `src/database/labeling.py`: leitura, simulação, aplicação, auditoria e fingerprints de preservação.
- `scripts/rotular_sprint5.py`: inventário, aplicar regras, importar revisão, auditar.
- `src/database/load_obras.py`: invalidar rótulos por mudança da fonte.
- `src/database/validation.py`: validar proveniência das decisões, opção estrita legada.
- `tests/test_labeling.py`, `tests/test_labeling_integration.py`: políticas, contratos e banco real.
- `specs/010-rotulagem-sprint5/`: spec, plan, research, data-model, contracts, quickstart, tasks e validation/report.
- `planos/Sprint5_Plano_de_Implementacao.md`, `docs/Sprints/Sprint5.md`, diário e próximos passos: acompanhamento local.

## Fases e entregáveis da sprint inteira
1. Protocolo e inventário: fonte PCC, distinção da ADR, regras conservadoras e inventário por causa/situação/base.
2. Motor de decisão: correspondência integral normalizada; razões de pendência; origem persistida como JSON no campo textual existente.
3. Revisão: fila e importação de decisões explícitas das quatro classes, com prova histórica e revisor declarado.
4. Persistência: transação integral, bloqueio de escrita concorrente nas duas tabelas fonte, simulação padrão, recusa de divergências e retomada.
5. Integração: invalidação no loader; auditoria de proveniência compatível com sprints anteriores.
6. Operação: inventário, baseline, aplicação real, reexecução e comparação de conteúdo; documentação e converge.

## Critérios de aceite e continuidade
Aceite técnico: comandos funcionam, rótulos inequívocos aplicados, pendências exportadas, repetição sem updates, corpus preservado e regressão real verde. Aceite científico permanece separado: revisor deve produzir exemplos regulares/ambíguos e homologar o protocolo; não há meta artificial de preencher 100% dos fatos.
Antes de treino: revisão humana, contraste 0–3, definição do horizonte, auditoria de fontes originais e vazamento, partições por obra e só então modelos de referência. Pendências T011/T013/T014 da feature 007 permanecem abertas.
