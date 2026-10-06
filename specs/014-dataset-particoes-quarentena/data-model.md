# Data Model: 014-dataset-particoes-quarentena

**Date**: 2026-10-01
**Feature**: [spec.md](spec.md)

## Entidades e Schemas

### 1. Entidade: ObservacaoConsolidada

Representa o grão fundamental do dataset analítico (uma observação por obra/data-base).

| Campo | Tipo | Descrição | Regras de Validação |
| :--- | :--- | :--- | :--- |
| `id_fato` | `int` | Chave primária da tabela `tcc.fato_risco` | Obrigatório, único |
| `id_tcu` | `str` | Identificador único canônico da obra | Obrigatório, chave de agrupamento |
| `ano` | `int` | Ano da data-base (2025 ou 2026) | 2025 ou 2026 |
| `base` | `str` | Base de origem (caixa, dnit, funasa, etc.) | Não nulo |
| `uf` | `str` | Unidade federativa da obra | 2 caracteres maiúsculos |
| `situacao_cadastral` | `str` | Situação física no corte histórico | Texto normalizado |
| `causa_cadastral` | `str | None` | Causa de paralisação cadastral original | Opcional |
| `label_risco` | `int | None` | Classe de risco homologada (0, 1, 2, 3 ou NULL) | Inteiro 0..3 ou NULL |
| `metodo_rotulagem` | `str` | Origem da rotulagem (`regra_situacao`, `regra`, `pendente`) | Não nulo |
| `valor_investimento` | `float` | Valor total de investimento/repasse contratado | $\ge 0$, preservado da dim_obra |
| `num_documentos_totais`| `int` | Quantidade total de documentos associados no banco | $\ge 0$ |
| `num_documentos_validos`| `int` | Quantidade de documentos pós-quarentena | $\ge 0$, $\le \text{totais}$ |
| `has_embedding` | `bool` | Indicador se a obra possui vetor documental válido | Booleano |
| `embedding` | `list[float]` | Vetor médio normalizado L2 | Array float32 com 768 dimensões |
| `particao` | `str` | Partição atribuída | `treino_dev`, `teste_retido`, `pendentes_2025`, `isolado_2026` |

---

### 2. Entidade: ManifestoParticionamento

Estrutura JSON de governança que acompanha os artefatos de dados exportados.

```json
{
  "versao_protocolo": "1.0.0",
  "data_geracao": "2026-10-01T23:00:00Z",
  "seed": 42,
  "algoritmo_particionamento": "StratifiedGroupSplit-80/20",
  "corte_historico_ano": 2025,
  "totais": {
    "total_banco": 60580,
    "total_2025": 28288,
    "total_rotulado_2025": 18154,
    "total_pendente_2025": 10134,
    "total_isolado_2026": 32292
  },
  "particoes": {
    "treino_dev": {
      "total_observacoes": 14523,
      "total_obras_unicas": 14523,
      "classes": { "0": 13319, "1": 782, "2": 83, "3": 339 },
      "has_embedding_pct": 54.2
    },
    "teste_retido": {
      "total_observacoes": 3631,
      "total_obras_unicas": 3631,
      "classes": { "0": 3330, "1": 196, "2": 21, "3": 84 },
      "has_embedding_pct": 54.1
    },
    "pendentes_2025": { "total_observacoes": 10134 },
    "isolado_2026": { "total_observacoes": 32292 }
  },
  "quarentena": {
    "documentos_excluidos": 36,
    "obras_afetadas": 22,
    "motivo": "Incompatibilidade contratual comprovada na Feature 012"
  },
  "vazamento_auditoria": {
    "intersecao_obras_dev_test": 0,
    "intersecao_obras_2026_treino": 0,
    "passou_auditoria": true
  },
  "arquivos_gerados": [
    {
      "nome": "dataset_treino_dev_2025.parquet",
      "sha256": "...",
      "linhas": 14523
    },
    {
      "nome": "dataset_teste_retido_2025.parquet",
      "sha256": "...",
      "linhas": 3631
    },
    {
      "nome": "dataset_pendentes_2025.parquet",
      "sha256": "...",
      "linhas": 10134
    },
    {
      "nome": "dataset_isolado_2026.parquet",
      "sha256": "...",
      "linhas": 32292
    }
  ]
}
```
