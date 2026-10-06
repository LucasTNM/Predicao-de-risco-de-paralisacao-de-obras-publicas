# Contrato
preparar_docker.py [--timeout SEGUNDOS]: prepara engine local e serviço postgres do compose.yaml; stdoutJSON, progresso/erro sanitizado emstderr; exit0 sucesso,2 falha. Não alterar contexto global nem arquivos do runtime.
ensure_postgres(root,timeout,progress): resultado com contexto e etapas acionadas; DockerRuntimeError informa estágio. Concorrência no mesmo processo é serializada.
connect(): primeiro tentar conexão padrão; se indisponível, apenas Windows+DSNloopback+porta gerenciada permite preparo e um retry. Autenticação falha, URL explícita e remoto não acionam preparo.
