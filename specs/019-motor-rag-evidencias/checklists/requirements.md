# Checklist de Requisitos: 019-motor-rag-evidencias

- [ ] Consultas causais definidas sem nenhum termo de situação ("paralisada", "em execução").
- [ ] Chunks de fichas sintéticas formalmente excluídos da recuperação.
- [ ] Recuperação restrita 100% aos fragmentos da própria obra consultada.
- [ ] Distância cosseno exata utilizada no pgvector (sem HNSW).
- [ ] Proveniência completa retornada para cada fragmento (id_documento, offsets, distância, consulta).
- [ ] Obras sem documentos retornam lista vazia e flag `sem_evidencia_textual = True`.
- [ ] Lotes congelados materializados para treino_dev e teste_retido com hashes SHA-256 em manifesto.
- [ ] Zero vazamento de id_tcu entre treino_dev e teste_retido.
- [ ] Relatório de cobertura por classe documentado.
