# Modelo de dados

Manifesto v1: modelo, revisão de pesos/código, normalização L2, seleção de
`id_embedding/chave_conteudo`, configuração de chunk, ano/origem, batch_size e
hash da seleção/configuração. IDs são únicos, limite 1..512, batch 1..32.
Nenhum texto ou vetor no manifesto. A execução associa versão e hash dos módulos.

Estados: PREPARADO → EM_EXECUCAO → CONCLUIDO ou INTERROMPIDO; dry-run INFERIDO.
Estado por item reflete commit confirmado. Reexecução confere o banco, podendo
recuperar commit não refletido no checkpoint e rejeitar corrupção mesmo se concluído.

Dossiê: id_documento, ano, origem registrada, hashes esperados/recalculados, coleta
aceita, URLs existentes, extração/limpeza, estado da cadeia. Candidato à revisão
não significa `original`; nunca atualizar origem sem decisão específica.
