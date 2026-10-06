> Atualização posterior: a feature [011](../011-situacao-causa-risco/plan.md) autoriza classe 0 pela situação sem contradições e adiciona recuperação de causas ausentes. Este documento preserva a etapa v1.

# Guia de validação

Executar na raiz, Docker saudável e .env local configurado; não imprimir credenciais.

```powershell
.venv/Scripts/python.exe scripts/rotular_sprint5.py inventariar --output logs/sprint5_inventario.json
.venv/Scripts/python.exe scripts/rotular_sprint5.py aplicar --output logs/sprint5_simulacao.json
.venv/Scripts/python.exe scripts/testar_sprint3.py
.venv/Scripts/python.exe scripts/rotular_sprint5.py aplicar --write --output logs/sprint5_aplicacao.json
.venv/Scripts/python.exe scripts/rotular_sprint5.py aplicar --write --output logs/sprint5_retomada.json
.venv/Scripts/python.exe scripts/rotular_sprint5.py auditar --output logs/sprint5_auditoria.json
```

Esperado: 2026 sem rótulos; reexecução zero atualizações; dados alheios ao alvo preservados. Cada saída deve usar nome novo. Distribuição com zero classe 0 não é falha do programa: impede declarar contraste pronto para treino.

## Revisão humana
Selecionar fato na fila do inventário, copiar id_fato e snapshot_sha256. Preparar arquivo UTF-8 da evidência original histórica/transcrição fiel, conferir a origem, calcular SHA-256 (`Get-FileHash -Algorithm SHA256`) e anotar data e trecho literal. Seguir data-model e exemplo abaixo. Não usar fichas sintéticas ou o próprio campo de causa como evidência de regularidade.

```json
{"decisoes": [{"id_fato": 123, "snapshot_sha256": "HASH_DA_FILA", "label_risco": 0, "revisor": "NOME_DO_REVISOR", "justificativa": "Fundamento da decisão após examinar evidência e conflitos", "regularidade_sem_apontamentos_graves": true, "evidencia": {"caminho": "evidencia_original.txt", "sha256": "HASH_DO_ARQUIVO", "data": "2025-01-01", "trecho": "TRECHO_LITERAL", "origem": "original"}}]}
```

O exemplo é formulário, não decisão real. Executar `revisar --input logs/revisoes.json --output logs/revisao_simulada.json`, conferir relatório e então repetir com --write e outro output. Identidade e interpretação são declarações do revisor; não há serviço de autenticação. Erros de data, hash, trecho, snapshot, classe ou id duplicado rejeitam todo lote. Preservar arquivos de evidência para auditorias futuras.
