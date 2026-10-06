# Implementation Plan: Inicialização autônoma do Docker
**Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)
## Summary
Usar docker desktop start --detach, sondar engine local e aguardar PostgreSQL saudável. Integrar ao runner e recuperar conexão padrão somente quando o serviço local estiver indisponível.
## Technical Context
Python3.14; subprocess/threading/socket/time/json padrão; Docker Desktop CLI instalada; Windows e PostgreSQL17 Compose existente. Sem dependência nova ou alteração DDL/políticas.
Orçamento global240s; subprocessos limitados ao restante. Progresso emstderr, sem DSN. Contexto desktop-linux explícito no Windows sem alterar contexto global. Container existente recebe compose start; ausente recebe up --no-recreate, com volume preservado.
## Constitution Check
I/II: fontes/políticas intactas. III: auditoria somente leitura. IV: testes simulados e ciclo real documentado, limites explícitos e integridade de dados. Gates pré/pós-design aprovados.
## Project Structure
- src/docker_runtime.py: supervisor.
- scripts/preparar_docker.py: comando.
- src/database/connection.py: preparo/retry para padrão local indisponível.
- scripts/testar_sprint3.py: preparo antes de banco descartável.
- tests/test_docker_runtime.py e tests/test_database_connection.py.
- AGENTS.md: instrução persistente.
- logs/docker_runtime/: evidências ignoradas.
## Execution
Pesquisa oficial delegada pelo speckit-plan; testes antes de implementar; ambiente ativo, ciclo frio controlado, auditoria antes/depois, regressões, atualização e converge.
