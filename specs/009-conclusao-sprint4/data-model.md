# Modelo de dados
Sem nova tabela. Dim_Embedding preserva chave/texto/token_ids/chunk_config; preenche vetor768, modelo e revisão.
Manifesto globalv1: data, modelo/revisões, dispositivo/dtype, batch/threads, contagem/hash da população, subarquivos com checksum, estado e progresso. Submanifestosv1 mantêm contrato008 e máximo512.
Estados PREPARADO, EM_EXECUCAO, INTERROMPIDO, CONCLUIDO. Sucesso global exige todos os submanifestos concluídos e validação posterior. Relações por ponte preservam ano/origem em filtros de busca.
Auditoria: contagens, erros, fingerprints não vetoriais, dimensões/normas/proveniência, comparação numérica e resultados de autocorrespondência. Logs não contêm credenciais e não são versionados.
