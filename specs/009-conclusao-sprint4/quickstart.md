# Validação ponta a ponta
1. Docker PostgreSQL saudável; testes ` .venv/Scripts/python.exe scripts/testar_sprint3.py`.
2. Auditar baseline com `scripts/auditar_embeddings_sprint4.py --recompute --device cpu` no venv de inferência.
3. Preparar corpus com `scripts/concluir_embeddings_sprint4.py --preparar --device cuda --inference-batch 8`.
4. Retomar manifesto retornado usando `--retomar <arquivo> --write`; repetir após falha preserva os commits anteriores.
5. Auditoria final deve mostrar zero pendentes e fingerprints iguais ao baseline.
6. `scripts/buscar_embeddings_sprint4.py --consulta "recursos financeiros da obra" --ano 2025`.
7. Executar validação integral das buscas, registrar mediana/percentil95 e relatório final; não converter similaridade em rótulo de risco.

Auditoria final executável: `scripts/auditar_embeddings_sprint4.py --recompute --sample 64 --stratified --device cuda --baseline logs/sprint4_009_baseline_gpu.json --output logs/sprint4_009_final_gpu.json`. Comparação com o baseline é obrigatória para o encerramento, além da cobertura integral.
