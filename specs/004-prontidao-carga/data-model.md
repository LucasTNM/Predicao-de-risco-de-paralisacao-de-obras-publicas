# Contrato dos relatórios

Nenhuma migração nas cinco tabelas de negócio.

- Relatório: início/fim, dry_run, escopo, status, progresso, anos, resultados.
- Ano: resumo de auditoria, fingerprints antes/depois de planilha e três manifestos,
  elegíveis com ano/base/PDF/TXT/obras/hashes observados; fontes_estaveis.
- Progresso: ano, verificados, total; não é inventário final nem homologação.
- Ocorrência: motivos existentes preservados. Destinação externa acrescenta
  decisão de manter fora do lote, evidência e condição de reentrada.

Estados: EM_EXECUCAO -> PREFLIGHT, ou INTERROMPIDO. Prontidão separada:
BLOQUEADO quando fontes variam ou há quarentena; APTO_COM_EXCLUSOES quando somente
exclusões; APTO quando completo sem ocorrências. Decisões revisadas podem liberar
somente o subconjunto elegível; nunca transformar quarentenas em elegíveis.
