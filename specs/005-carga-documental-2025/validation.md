# Relatório de Validação e Auditoria da Carga Documental — 2025

## 1. Estado Final da Carga

* **Status**: `CONCLUIDO`
* **Prontidão das Fontes**: `APTO`
* **Data/Hora de Conclusão**: `2026-09-15T20:03:55-03:00`
* **Relatório Operacional**: `logs/sprint3_20260915_195827_204095.json`
* **Tempo Total de Carga**: 240 segundos (~4 minutos) para 15.408 documentos.

---

## 2. Comparativo do Banco de Dados (Antes vs Depois)

| Tabela / Métrica | Baseline Pré-Carga | Estado Pós-Carga | Variação (Delta) |
| :--- | :---: | :---: | :---: |
| `tcc.dim_obra` | 28.288 | 28.288 | 0 (preservado) |
| `tcc.fato_risco` | 28.288 | 28.288 | 0 (preservado) |
| `tcc.dim_documento` | 45 | **15.408** | **+15.363** (+ 45 reutilizados) |
| `tcc.dim_embedding` (chunks únicos) | 205 | **24.437** | **+24.232** |
| `tcc.ponte_documento_embedding` | 207 | **24.883** | **+24.676** |
| **Falhas de Carga** | - | **0** | **100% de sucesso** |

---

## 3. Auditoria de Integridade Relacional (`validate_data`)

A verificação executada via `src/main.py --modo validar-banco` com conexão somente leitura atestou conformidade total:

* **Validade Global**: `valido: True`
* **Inconsistências Detectadas**:
  * `obra_sem_fato`: **0**
  * `fragmento_sem_ponte`: **0**
  * `documento_incompleto`: **0**
  * `offset_ou_tokens_inconsistentes`: **0**
  * `posicao_documental_inconsistente`: **0**
  * `vetor_preenchido_antes_card8`: **0** (todos os vetores permanecem `NULL`)
  * `rotulo_preenchido_sem_homologacao`: **0** (todos os labels permanecem `NULL` / `PENDENTE`)
  * `conteudo_hash_inconsistente`: **0**
  * `cobertura_tokens_inconsistente`: **0**

---

## 4. Testes de Regressão

* Execução do script oficial de homologação: `scripts/testar_sprint3.py`.
* Resultado: **56 passed in 6.48s**.
* Zero regressões de catálogo, chunking, schema drift ou preflight.

---

## 5. Auditoria de 2026

* Em 2026-09-15, o preflight físico isolado dos 35.602 arquivos de 2026 iniciou em paralelo; essa execução ficou parcial em 34.000/35.602.
* Em 2026-09-16, o preflight integral foi repetido e concluído, seguido da carga dos 35.601 documentos elegíveis de 2026. Ver `specs/006-carga-documental-2026/validation.md`.
