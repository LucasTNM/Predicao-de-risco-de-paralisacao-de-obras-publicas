# Resultado — inicialização autônoma Docker
**Data:** 2026-09-30. **Fluxo:** SpecKit specify → plan/pesquisa → tasks → implement → converge.

## Comportamento entregue
O supervisor usa [docker desktop start --detach](https://docs.docker.com/reference/cli/docker/desktop/start/) quando o engine local está indisponível. Solicita início uma vez, verifica engine e aguarda healthcheck do PostgreSQL dentro do orçamento global240s. Subprocessos têm limite individual e progresso por etapa. Contexto local é explícito, sem alterar contexto global.

Com ambiente saudável, reutiliza engine/container. Serviço existente parado recebe compose start; criação só quando ausente, com --no-recreate. Não altera sockets, volumes ou distribuições. O runner scripts/testar_sprint3.py prepara antes de provisionar banco descartável. A conexão padrão local recupera serviço indisponível e tenta conectar novamente; URL explícita, banco remoto e erro de autenticação não acionam Docker.

Comando: scripts/preparar_docker.py. Instrução permanente para futuras sessões: AGENTS.md.

## Validação real
Antes do teste, havia somente tcc-sprint3-postgres-1 ativo e nenhuma outra consulta ativa no banco. Baseline de60.580 observações registrado. Docker Desktop foi encerrado pela CLI apenas nessa janela controlada; docker info confirmou engine indisponível. Em seguida, somente connect() padrão do projeto foi chamado.

**Resultado:** Desktop iniciado autonomamente, engine/PostgreSQL saudáveis e conexão pronta em21,892s. Digest das60.580 observações completas idêntico antes/depois; auditoria de proveniência válida. Evidência: logs/docker_runtime/ciclo_frio.json. Ambiente ativo reusado depois sem novo comando de início, em0,879s. Docker/PostgreSQL deixados operacionais.

Regressão integral: **214 testes aprovados em 8,64s**, incluindo 17 novos testes de runtime/conexão e PostgreSQL real descartável. Cobertura funcional: início solicitado uma vez, timeout, autenticação, contexto remoto (inclusive named pipe remoto), URL explícita, container ausente, cache de ambiente ativo, prazo finito e sondagem temporariamente lenta. Testes são distintos da demonstração real de startup.

## Convergência SpecKit
Resultado final: converged, sem novas tarefas. Verificados 7 requisitos funcionais, 4 critérios de sucesso, 6 cenários de aceitação, decisões do plano e 4 princípios da constituição. A lacuna de named pipe remoto encontrada na primeira passagem foi corrigida em T009 e coberta por teste que falhou antes da correção e passou depois. T001–T009 concluídas; tasks.md permaneceu inalterado na conferência final. Features012/013 têm validação técnica concluída; isso não encerra as pendências científicas de evidência causal da sprint.

## Limites
O erro anterior sailor-ingest.sock não reapareceu no ciclo frio pela CLI; isso demonstra eficácia nesta sessão, sem comprovar sua causa raiz ou reparo permanente de defeitos internos do Docker Desktop. Instalação quebrada, falta de permissão ou engine que não chega à prontidão continuam produzindo falha por etapa. A rotina não executa reparos destrutivos nem garante startup em qualquer instalação.

## Retomada da Sprint5
Feature012 teve T010/T013 concluídas:197 testes iniciais passaram e auditoria somente leitura confirmou observações/rótulos iguais à população do piloto, com0 rótulos em2026. O ciclo frio também confirmou preservação. Piloto segue com82 casos processados,28 identidades confirmadas,0 causas históricas elegíveis e0 novos rótulos; pendências científicas permanecem em [revisao.md da feature012](../012-piloto-recuperacao-causal/revisao.md).
