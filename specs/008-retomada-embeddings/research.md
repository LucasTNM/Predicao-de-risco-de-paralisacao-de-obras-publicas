# Pesquisa e decisões

1. **Decisão:** reutilizar conexão, GTE e contratos da 007. **Motivo:** já testados;
   **alternativa:** novo backend/modelo criaria mistura e não resolve proveniência.
2. **Decisão:** banco como fonte de verdade para retomada, seleção congelada no JSON.
   **Motivo:** commit pode preceder falha no relatório; **alternativa:** confiar em
   lista de concluídos perde itens ou faz sobrescrita. Revalidar todos os itens no retorno.
3. **Decisão:** transação externa por lote, locks ordenados. **Motivo:** rollback
   integral sem aumentar muito memória; **alternativa:** commit por item não é lote atômico.
4. **Decisão:** dossiê somente leitura. **Motivo:** URLs de coleta e PDF local com hash
   consistente são rastreabilidade, mas não homologam originalidade/relevância sozinhos.
5. **Pesquisa independente:** auditoria local das 27 quarentenas pela etapa de pesquisa
   speckit-plan; resultado em `logs/sprint3_reauditoria_quarentenas_20260920.json`.

Sem nova dependência ou consulta externa necessária nesta etapa; contratos existentes
e código instalado são a base técnica. Docker Desktop local precisa estar ativo.
