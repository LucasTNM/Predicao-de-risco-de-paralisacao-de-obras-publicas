# Implementation Plan: Prontidão da carga
**Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)

## Summary
Auditar os dois anos, publicar evidência integral e decidir destinação conservadora
antes de qualquer carga. Corrigir relatórios longos e documentação operacional.

## Technical Context
Python 3.14 / PowerShell; dependências fixadas existentes; PostgreSQL 17/pgvector.
Corpus no Drive somente leitura; relatórios JSON locais em logs/ ignorados.
Pytest e integração descartável; sem mudanças de DDL, tokenizer ou corpus.
Escala atual: 51.234 textos manifestados e 60.580 observações de obras.
Performance: manter cinco leitores e lotes limitados, com progresso periódico.

## Constitution Check
I: não inferir rótulos nem promover fichas sintéticas a originais.
II: rejeitados/ambíguos ficam fora do lote; preservar proveniência e hashes.
III: manter cinco tabelas, contrato 450/50 e vetores NULL.
IV: relatórios atômicos, testes, corpus/segredos/logs fora do Git.
Gates antes/depois do desenho: aprovados; nenhum desvio metodológico.

## Project Structure
- src/database/run_load.py: checkpoint de progresso, inventário e hashes de fontes.
- tests/test_database_reporting.py: interrupção, dry-run sem conexão e fontes alteradas.
- src/main.py: esclarecer anos no help, saída bloqueada e conexão de validação somente leitura.
- A carga futura bloqueia antes da conexão se houver quarentena; opção explícita
  --excluir-quarentena permite apenas o subconjunto elegível e registra a decisão.
- specs/004-prontidao-carga/: especificação, decisões, plano, tarefas e validação.
- docs/Sprints/Sprint3.md e quickstart.md: corrigir sequência operacional.
- logs/: relatórios, inventário e destinação detalhada por arquivo (não versionar).

## Implementation Strategy
Testes de regressão primeiro; correção restrita dos relatórios; executar preflight
integral com dry_run=True. Inspecionar ocorrências por fonte; não fabricar dados.
Persistir relatório de destinação e evidências resumidas versionáveis. Confirmar
banco sem alteração e consolidar código local revisado sem publicação remota.

## Complexity Tracking
Sem tabelas, serviços ou dependências novas. Não implementar retomada que confie
em cache sem revalidar bytes; um relatório anterior não autoriza carga posterior.
