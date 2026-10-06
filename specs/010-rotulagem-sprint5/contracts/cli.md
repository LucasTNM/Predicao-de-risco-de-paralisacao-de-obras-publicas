# Contrato CLI — scripts/rotular_sprint5.py

Comandos: `inventariar --output ARQUIVO`, `aplicar --output ARQUIVO [--write]`, `revisar --input ARQUIVO --output ARQUIVO [--write]`, `auditar --output ARQUIVO`.

Simulação padrão; só --write altera banco. Output deve ser novo arquivo, publicado atomicamente; não sobrescrever evidências de execução anterior. UTF-8 JSON, sem credenciais; exit 0 sucesso, 2 erro. Erro de lote não confirma escrita. --input obrigatório só em revisar; conteúdo: objeto {decisoes: [revisoes]}. Duplicação de id_fato invalida lote. Caminhos de evidência relativos resolvidos pela pasta do arquivo de entrada e persistidos absolutos.

Inventário: todos os fatos separados por ano; fila de 2025 com snapshot_sha256, campos de contexto, decisão sugerida/motivo e rótulo persistido. Revisão exige campos do data-model; classe 0 não pode vir das regras. Aplicação revalida estado sob lock, atualiza apenas rótulo/origem/status/updated_at e não substitui decisão divergente. Preservação e validação entram no relatório.
