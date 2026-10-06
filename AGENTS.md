# Instruções do projeto TCC

## Fluxo de trabalho
Usar SpecKit para especificar, planejar, gerar tarefas, implementar e verificar convergência. Preservar histórico das features e atualizar documentos da sprint. Seguir `.specify/memory/constitution.md`; políticas de rotulagem históricas com hash são imutáveis.

## Docker e PostgreSQL local
Antes de comandos que dependem do banco, executar da raiz:
```powershell
.\.venv\Scripts\python.exe scripts/preparar_docker.py
```
A rotina usa a CLI oficial `docker desktop start --detach` quando necessário, aguarda engine local e saúde do PostgreSQL e reutiliza ambientes ativos. O runner `scripts/testar_sprint3.py` já prepara o ambiente. A conexão padrão também recupera o serviço local indisponível; URLs explícitas de teste/remotas não acionam startup.

Usar a rotina existente em vez de lançar diretamente o executável Desktop ou encerrar processos à força. Falhas internas de inicialização exigem diagnóstico do produto; não manipular sockets, volumes, distribuições WSL ou configurações para tentar resolver o problema. Não parar/reiniciar ambientes ativos durante trabalho normal. Testes de ciclo de vida reais exigem janela controlada sem outras cargas.

## Validação e dados
Testes de integração usam o banco descartável criado pelo runner. Auditorias de produção são somente leitura. Credenciais, corpus e logs locais ficam ignorados pelo Git; não imprimir `.env` ou configuração Compose expandida.
