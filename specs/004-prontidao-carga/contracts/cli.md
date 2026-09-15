# Contrato operacional

`python -m src.main --modo carga --dry-run --ano 2025` audita um ano.
Omitir --ano em carga audita 2025 e 2026. Não usar filtros/limites para homologação
integral. Dry-run retorna antes de abrir conexão de carga.

Relatório local atômico é publicado no início, em cada progresso e ao concluir ano.
PREFLIGHT não equivale a APTO. Quarentenas devem ter destinação documentada.
Fonte alterada durante auditoria bloqueia prosseguimento e exige nova auditoria.
Na carga futura os arquivos são novamente validados; --force não revoga rejeições.

CLI retorna código 2 para parecer BLOQUEADO ou carga PARCIAL; isso não significa
que a auditoria foi interrompida. Conferir status e parecer no relatório.
`--modo validar-banco` abre conexão explicitamente somente leitura.

Na carga futura (sem --dry-run), quarentenas bloqueiam antes de conectar ao banco.
Depois da revisão da destinação, --excluir-quarentena autoriza exclusivamente os
documentos elegíveis; quarentenas permanecem no relatório e fora da carga. Não usar
essa opção para simular aprovação do corpus completo. Nenhum elegível bloqueia a carga.
