# Validação da carga documental de 2026

## Evidências de entrada

- Carga de 2025: `logs/sprint3_20260915_195827_204095.json`, status `CONCLUIDO`, 15.408 documentos; integridade válida.
- Banco antes de 2026: `logs/carga_2026_banco_antes.json`; somente 2025 (28.288 obras/fatos, 15.408 documentos, 24.437 fragmentos, 24.883 vínculos), nove verificações zeradas.
- Preflight anterior de 2026: `logs/sprint3_20260915_195745_374578.json`, parcial em 34.000/35.602; não é homologação.
- Preflight atual: `logs/sprint3_20260916_173511_576032.json`, `PREFLIGHT`, 35.602/35.602 arquivos conferidos, fontes tabulares estáveis.
- Manifesto atual: 35.826 textos; 35.601 elegíveis; 225 ocorrências: 198 `coleta_nao_aceita` excluídas, 23 `coleta_ausente`, 3 `vinculo_multiplo_nao_homologado` e 1 `qualidade_residual` em quarentena.
- Destinação individual: `logs/carga_2026_destinacao.json`. Todas as 225 ocorrências permanecem fora do lote, com motivo e condição de reentrada. As três ambiguidades SIMEC não foram promovidas a vínculo válido.
- Regressão: `scripts/testar_sprint3.py`, 56 passed.

## Carga

Executada por `python -m src.main --modo carga --ano 2026 --excluir-quarentena`.
O processo repetiu o preflight físico antes da escrita, com o mesmo hash do inventário de 35.601 elegíveis e fontes tabulares estáveis. Relatório operacional: `logs/sprint3_20260916_174227_445463.json`.

Resultado: 35.601 documentos carregados, 208.019 ocorrências de chunks/vínculos de 2026, zero falhas. O status operacional é `PARCIAL` e a prontidão é `BLOQUEADO` porque 27 quarentenas continuam pendentes, mesmo mantidas fora do lote por `--excluir-quarentena`. O código de saída não representa falha de escrita; preservar o estado parcial evita declarar o corpus completo homologado.

## Validação independente após a carga

Evidência em `logs/carga_2026_banco_depois.json`, obtida em conexão somente leitura:

| Métrica | 2025 | 2026 | Total |
|---|---:|---:|---:|
| Obras e fatos | 28.288 | 32.292 | 60.580 |
| Documentos | 15.408 | 35.601 | 51.009 |
| Vínculos | 24.883 | 208.019 | 232.902 |
| Fragmentos únicos | — | — | 185.789 |

O inventário esperado e os registros de 2026 coincidem exatamente: 35.601 esperados e 35.601 gravados, zero faltantes, zero extras e zero dos 225 excluídos presentes. A assinatura agregada dos 15.408 documentos de 2025 é idêntica ao baseline.

`validate_data` retornou `valido: true` e zero nas nove inconsistências, inclusive vetores preenchidos e rótulos preenchidos. A carga documental não homologa treinamento com dados de 2026.

> **Estado posterior:** no fechamento da Sprint 3, todos os vetores eram nulos.
> Em 2026-09-16, a Sprint 4 gravou um piloto de 17 vetores, documentado
> em artefatos locais dessa sprint, fora deste commit. Os rótulos seguem nulos.

## Convergência Speckit

FR-001..FR-006 e SC-001..SC-004 conferidos contra preflight, relatórios e banco. Nenhuma tarefa de implementação pendente; o estado `PARCIAL` registra as quarentenas preservadas, já destinadas individualmente.
