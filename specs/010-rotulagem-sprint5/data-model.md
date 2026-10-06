# Modelo de dados

Sem migração: `dim_obra` e `fato_risco` preservam o DDL existente.

- Snapshot por `id_fato`: id_obra, ano_base, base_de_dados, id_tcu, data_base, situacao/situacao_origem, fonte integral, causa e medidas. Hash SHA-256 canônico; exclui rótulo e timestamps de execução.
- `label_risco`: inteiro exato em {0,1,2,3} ou NULL; booleanos proibidos.
- `status_rotulagem`: NULL => PENDENTE; rótulo => ROTULADO, mantendo CHECK existente.
- `origem_rotulo`: JSON textual canônico com schema `sprint5/v1`, método `regra` ou `revisao`, versão/hash política, snapshot hash, id_fato, classe, autoria do processamento e timestamp UTC; regra ou decisão humana completa. NULL enquanto pendente.
- Revisão: id_fato único, snapshot_sha256, label_risco, revisor e justificativa não vazios, evidencia {caminho, sha256, data, trecho, origem=original}, regularidade_sem_apontamentos_graves=true obrigatória para zero. Evidência não posterior à data-base da observação de 2025.
- Execução: totais, por ano/base/classe/motivo, hashes das tabelas e lista de decisões. Logs locais ignorados pelo Git.

Transições: PENDENTE -> ROTULADO após validação transacional; ROTULADO -> reuso se decisão igual; divergência -> erro sem update; alteração do contexto no loader -> PENDENTE com origem nula. Histórico anterior permanece nos relatórios locais de cada execução. Não há atualização de classe divergente nem revogação arbitrária nesta versão.
