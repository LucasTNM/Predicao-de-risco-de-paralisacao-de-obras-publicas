# Modelo de dados: piloto de embeddings

- `tcc.dim_embedding`: uma linha por conteúdo canônico; `id_embedding`, `chave_conteudo`, `conteudo_chunk`, `token_ids`, `chunk_config` permanecem imutáveis no Card 8. `embedding vector(768)`, `modelo_embedding` e `revisao_embedding` são preenchidos juntos.
- `tcc.ponte_documento_embedding`: continua relacionando cada ocorrência documental ao conteúdo único; nenhuma escrita planejada no piloto.
- Manifesto local de execução: modelo, SHA, versões, prefixo, normalização, IDs processados, status e tempos, sem texto nem credenciais. Persistir sucesso somente após commit.
- Relatório de auditoria: total, distribuição dos comprimentos E5, máximo, excedentes e hashes de modelo/código; sem mutação no banco.

Estados de uma linha: `PENDENTE` (`embedding IS NULL`) → `VETORIZADA` (vetor/modelo/revisão completos). Vetor de modelo/revisão incompatível bloqueia reuso e exige migração explícita.
