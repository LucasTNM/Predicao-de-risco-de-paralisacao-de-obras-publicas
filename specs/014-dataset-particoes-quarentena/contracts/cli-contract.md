# Interface Contract: CLI de Preparação de Datasets

**Feature**: [spec.md](../spec.md)

## Comando: `scripts/preparar_dataset_sprint6.py`

Rotina que extrai as observações do banco PostgreSQL, aplica agregação vetorial com quarentena dos 36 documentos DNIT, particiona sem vazamento por grupo de obra e gera os artefatos de dados e o manifesto.

### Assinatura CLI

```bash
python scripts/preparar_dataset_sprint6.py [OPÇÕES]
```

### Argumentos e Opções

| Parâmetro | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `--output-dir` | Caminho | `dados_processados/sprint6` | Diretório de destino dos arquivos Parquet e manifesto JSON |
| `--seed` | Inteiro | `42` | Semente determinística para a divisão pseudo-aleatória |
| `--test-ratio` | Float | `0.20` | Proporção de obras no conjunto de teste reservado |
| `--skip-vectors` | Flag booleana | `False` | Se informado, extrai apenas dados tabulares (para preflight rápido) |
| `--auditar-vazamento` | Flag booleana | `True` | Executa verificação matemática estrita de interseção vazia de grupos |

### Formato de Saída (STDOUT)

Saída estruturada em JSON na última linha contendo:
```json
{
  "sucesso": true,
  "total_processado": 60580,
  "particoes": {
    "treino_dev": 14523,
    "teste_retido": 3631,
    "pendentes_2025": 10134,
    "isolado_2026": 32292
  },
  "quarentena_aplicada": 36,
  "vazamento_detectado": false,
  "manifesto": "dados_processados/sprint6/manifesto_particionamento.json",
  "tempo_segundos": 14.85
}
```

### Códigos de Retorno (Exit Codes)

- `0`: Sucesso integral, arquivos gravados e auditados sem vazamento.
- `1`: Erro de conexão com banco de dados ou ambiente Docker indisponível.
- `2`: Detecção de vazamento de identidade de obras entre treino e teste.
- `3`: Inconsistência de cardinalidade com o banco de dados.
