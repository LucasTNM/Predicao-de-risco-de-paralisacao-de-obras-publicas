# CLI de validação da Sprint 3

| Comando | Contrato |
| --- | --- |
| `python -m src.main --modo carga --ano 2025 --dry-run` | Audita fontes físicas e gera somente relatório local |
| `python -m src.main --modo carga --ano 2025 --limit 5` | Até cinco documentos por base; resultado parcial por definição |
| `python -m src.main --modo carga --ano 2025 --force` | Substituição transacional de documentos já carregados |
| `python -m src.main --modo validar-banco` | Consulta schema/dados; exit 0 válido ou 1 inconsistente |
| `python -m src.main --modo schema` | Aplica schema vazio preparado ou valida existente; recusa drift |
| `python scripts/testar_sprint3.py` | Cria banco local exclusivo, roda Pytest e remove somente esse banco |

Carga parcial retorna exit 2. Exceções fatais e falhas persistentes de relatório
não podem produzir sucesso. Credenciais não aparecem nos relatórios.
`--dry-run` não homologa carga nem executa tokenização massiva ou embeddings.
