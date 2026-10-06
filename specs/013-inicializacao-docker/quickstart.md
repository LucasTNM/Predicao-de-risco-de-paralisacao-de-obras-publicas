# Uso
```powershell
.\.venv\Scripts\python.exe scripts/preparar_docker.py
.\.venv\Scripts\python.exe scripts/testar_sprint3.py
```
Timeout padrão240s. Progresso emstderr e resultadoJSON emstdout. Runner prepara o ambiente antes do banco descartável. A conexão padrão local prepara/reconecta quando o serviço não está disponível. URL explícita/remota não aciona preparo.
