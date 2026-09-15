# Preparação antes da carga

Na raiz do projeto, PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database_reporting.py tests/test_database_preflight.py tests/test_chunker.py -q
.\.venv\Scripts\python.exe -m src.main --modo carga --dry-run
```

Aguardar término dos dois anos e revisar relatório de logs/. Em interrupção,
progresso parcial não homologa arquivos. Não executar carga sem dry-run nesta etapa.

Sequência: preflight físico integral -> destinação de exclusões/quarentenas ->
carga documental e chunks (autorização posterior) -> embeddings/Card 8.
Fichas sintéticas e snapshots 2026 não recebem autorização de treinamento por
serem elegíveis para armazenamento. Revalidar fontes novamente na carga futura.
