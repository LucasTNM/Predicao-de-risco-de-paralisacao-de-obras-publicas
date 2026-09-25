# Validação

1. Iniciar Docker Desktop e o serviço local de PostgreSQL já configurado.
2. `.venv/Scripts/python.exe scripts/testar_sprint3.py` (banco descartável).
3. `.venv/Scripts/python.exe scripts/auditar_proveniencia_sprint3.py` (somente leitura).
4. `.venv-sprint4/Scripts/python.exe scripts/gerar_embeddings_sprint4.py --limite 32 --ano 2025 --origem nao_confirmada --write`.
5. Retomar o manifesto indicado via `--retomar <arquivo> --write`: nenhuma nova inferência.
6. Conferir validação operacional e relatório de quarentenas. Manter pendências
   de origem/relevância da 007 quando a evidência for insuficiente.
