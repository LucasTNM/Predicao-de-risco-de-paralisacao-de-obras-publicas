# Guia de validação: primeiro piloto de embeddings

1. Conferir `python -m src.main --modo validar-banco` e o baseline atual. Em 16/09 havia 185.789 chunks e 17 vetores; não esperar todos nulos após o piloto.
2. Executar `.\.venv\Scripts\python.exe scripts/auditar_tokens_sprint4.py --candidato e5` e depois `--candidato gte`; revisar os dois relatórios.
3. Revisar relatório: total igual ao banco, distribuição completa e excedentes explícitos. Nenhum truncamento é permitido.
4. Instalar `requirements-sprint4.txt` em `.venv-sprint4`; executar `.\.venv-sprint4\Scripts\python.exe scripts/piloto_embeddings_sprint4.py` para inferência em leitura e `--write` para gravar o mesmo piloto após testes.
5. Comparar integridade antes/depois, modelo/revisão, recursos e casos de busca revisados; registrar a decisão de escala.

## Busca e revisão semântica

Executar na raiz, em PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/testar_sprint3.py
.\.venv-sprint4\Scripts\python.exe -m pytest tests/test_sprint4.py -q
.\.venv-sprint4\Scripts\python.exe scripts/piloto_embeddings_sprint4.py --por-estrato 8 --write
.\.venv-sprint4\Scripts\python.exe scripts/avaliar_busca_sprint4.py --ano 2025 --k 5
.\.venv-sprint4\Scripts\python.exe scripts/avaliar_busca_sprint4.py --ano 2026 --k 5
```

O runner completo depende da `.venv` da Sprint 3 (PDFs/planilhas/NLP). A `.venv-sprint4`
é isolada para inferência; instalar nela `requirements-sprint4.txt`.

No pacote `logs/sprint4_revisao_*.json`, revisar o universo completo e preencher em cada
consulta `revisado_por`, `universo_revisado_integralmente: true` e `relevantes: [IDs]`.
Preencher também `tipo_revisao` na raiz: `humana` ou `assistida_ia`. O script rejeita
tipo ausente e distingue `AVALIADO_COM_JULGAMENTOS` de `AVALIADO_ASSISTIDO_IA`.
Lista vazia significa nenhum relevante no piloto. Manter assinatura/consultas intactas.
Reexecutar a busca com mesmos ano/origem/consultas e `--julgamentos <arquivo>`.
As métricas descrevem apenas esse universo; não extrapolar qualidade ao corpus inteiro.

## Benchmark de custo por comprimento (somente leitura)

```powershell
.\.venv-sprint4\Scripts\python.exe scripts/benchmark_embeddings_sprint4.py --container tcc-sprint3-postgres-1 --por-faixa 8 --repeticoes 3
```

O container deve ser o PostgreSQL configurado para este projeto. O script confirma
que PGDATA corresponde a volume nomeado e mede seu filesystem via `df`. Conferir
também o espaço físico do host Docker: espaço virtual livre não garante crescimento
do VHDX. Relatórios em `logs/sprint4_benchmark_*.json`; nenhum vetor é persistido.

As consultas com `--origem original` atualmente não encontram candidatos no piloto.
`--origem nao_confirmada` é somente um recorte exploratório, sem promover proveniência.
