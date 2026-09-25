# Implementation Plan: Conclusão da Sprint 4
**Date**: 2026-09-23 | **Spec**: [spec.md](spec.md)
## Summary
Reauditar baseline, concluir carga congelada de todos os chunks aceitos e validar busca exata por cosseno no PostgreSQL. Usuário autorizou a execução integral; preservar explicitamente pendências científicas de 007.
## Technical Context
Python3.14, psycopg3, PostgreSQL17/pgvector, GTE Alibaba multilingual base 768/L2, modelo/revisões de 007. CPU Ryzen5700X; RTX5060 8GB disponível. Testar CUDA13/PyTorch2.14 float32 em venv separado, preservando ambiente CPU. Não usar fp16 ou TF32. GPU só após comparação numérica aprovada; CPU8threads é fallback.
## Constitution Check
I: não treinar/classificar nem alterar rótulos/origem/ano. II: nenhum truncamento ou modificação do corpus. III: sem DDL necessário para busca exata; fingerprints das colunas não vetoriais preservadas. IV: versões, dispositivo, duração, checksums, logs atômicos e lotes transacionais; reuso conferido no banco.
## Design / Project Structure
- `scripts/auditar_embeddings_sprint4.py`: baseline/final, integridade, estatísticas, fingerprints e recomputação opcional dos vetores presentes.
- `src/database/embedding_corpus.py`: seleção integral congelada, submanifestos <=512 com checksum, lock global, continuidade pelo banco e modelo único; cada submanifesto mantém contrato008.
- `scripts/concluir_embeddings_sprint4.py`: preparar/retomar, modo write explícito, dispositivo e batch de inferência1..32, threads1..16; proteção de disco e logs incrementais.
- `src/embedding_model.py`: dispositivo opcional CPU/CUDA, precisãofloat32, parâmetros explícitos; padrãoCPU preservado.
- `src/database/embedding_run.py`: registrar dispositivo/batch reais; sem relaxar limite512.
- `scripts/buscar_embeddings_sprint4.py`: consulta textual, ano/origem/k, relatório com ranking/proveniência, tempo de inferência e SQL.
- `scripts/validar_busca_integral_sprint4.py`: autocorrespondência e filtros com vetores do banco, consultas temáticas, latência e decisão índice.
- `tests/test_sprint4_corpus.py`, integração PostgreSQL: corrupção/checkpoints/revisãoNULL/filtros.
## Decisions
Buscar exatamente antes de otimizar; alvo operacional exploratório mediana <=5s por consulta SQL local, sem prometer SLA. Se exceder, investigar plano/buffers e índice, com migração explícita e comparação de recall antes de mudar o padrão.
Comparação numérica: cosine >=0.99999 e erro absoluto máximo <=0.0001 para float32; registrar mínimos/máximos. Auditoria física de arquivos já aceita não será confundida com validação semântica. Todos os vetores finais são verificados; recomputação inicial157 integral e amostrafinal por faixas/ano/origem.
## Complexity Tracking
Nenhuma migração de esquema inicialmente. Manifesto global contém subarquivos e checksums, nunca todos os textos/vetores. Reutilização é feita por read_items com conteúdo/token/config/modelo; conflitos falham. Falha de log depois do commit não causa perda na retomada.
