# Relatório final — Sprint 4: embeddings e busca vetorial

**Data:** 2026-09-23
**Estado:** CONCLUÍDA TECNICAMENTE
**Objetivo entregue:** executar um modelo aberto do Hugging Face sobre todos os chunks elegíveis já carregados, alimentar `tcc.dim_embedding` e disponibilizar busca por vetores no PostgreSQL.

## 1. Resultado confirmado no banco

| Métrica | Antes | Depois |
|---|---:|---:|
| Chunks únicos | 185.789 | 185.789 |
| Vetores preenchidos | 157 | **185.789** |
| Vetores pendentes | 185.632 | **0** |
| Vetores inválidos | 0 | **0** |
| Documentos | 51.009 | 51.009 |
| Obras / fatos | 60.580 / 60.580 | 60.580 / 60.580 |
| Vínculos documentais | 232.902 | 232.902 |
| Rótulos preenchidos | 0 | 0 |

Foram gerados **185.632 vetores novos** e reutilizados exatamente os **157 vetores do baseline**. A cobertura dos chunks elegíveis é **100%**. As exclusões/quarentenas da Sprint 3 permanecem fora do corpus; esse fechamento não altera sua destinação.

## 2. Modelo, configuração e reprodutibilidade

- Modelo: `Alibaba-NLP/gte-multilingual-base`, licença Apache-2.0.
- Revisão dos pesos: `9bbca17d9273fd0d03d5725c7a4b0f6b45142062`.
- Revisão do código externo: `40ced75c3017eb27626c9d4ea981bde21a2662f4`.
- Vetor: 768 dimensões, normalização L2, sem prefixo adicional.
- Janela: 8.192 tokens; maior entrada nova observada: 4.580 tokens, sem truncamento.
- Execução: RTX 5060, PyTorch 2.14.0+cu130, float32, TF32 desligado, 8 threads CPU.
- Inferência em batches de 8; transações de até 32; 363 submanifestos de até 512 chunks.
- Dependências GPU fixadas em `requirements-sprint4-gpu.txt`; ambientes CPU e principal preservados.

A seleção foi congelada por ID, chave de conteúdo e configuração. Cada lote revalida conteúdo/tokens/configuração sob bloqueio, grava vetor e proveniência atomicamente e publica o checkpoint após o commit. A retomada consulta o banco, inclusive quando o relatório anterior está atrasado.

## 3. Auditoria independente

**Baseline:** os 157 vetores existentes foram recomputados em GPU e comparados aos valores persistidos. Todos passaram: cosine mínimo 0.999999999985, maior diferença absoluta 6.037e-07.

**Resultado final:** todos os 185.789 vetores foram conferidos quanto a cobertura, dimensão, modelo/revisão e norma. Normas entre 0.9999999026 e 1.0000001246. O tipo pgvector rejeita valores não finitos; a persistência também valida finitude e normalização.

Uma amostra final de **64 conteúdos** foi recomputada em **CPU**: estratos de ano, origem e faixa WordPiece, extremos de tamanho textual e complemento determinístico. Todos passaram, com cosine mínimo 0.999999999988 e diferença absoluta máxima 6.438e-07. Os limites definidos antes da execução eram cosine ≥ 0,99999 e erro máximo ≤ 0,0001. A recomputação final é amostral; a verificação estrutural/vetorial e os hashes de conteúdo cobrem o corpus inteiro.

Os fingerprints das **cinco tabelas** são idênticos ao baseline, excluindo apenas os campos de vetor/modelo/revisão em `dim_embedding`. Textos, tokens, configuração, documentos, offsets, vínculos, fatos e rótulos permaneceram preservados. `validate_data` retornou válido, com todas as verificações zeradas.

## 4. Execução e retomada

- Carga completa: **3.346,35 segundos (55 min 46 s)**, incluindo inferência, persistência e checkpoints.
- Vazão efetiva de novos vetores: **55,47 chunks/s**.
- Pico de memória alocada no CUDA: **3,42 GiB**.
- Memória RSS do processo na última medição: **1,60 GiB**; esse valor não é o pico RSS.
- Tamanho total de `dim_embedding`, incluindo índices e TOAST: **1.408.409.600 bytes**.
- Retomada integral após a carga: **185.789 reutilizados, 0 gravados**, em **95,04 segundos**, sem carregar o modelo para inferência.

O Docker precisou ser recuperado antes da carga e reiniciado antes da conferência final. As verificações que falharam por conexão foram reexecutadas após o PostgreSQL ficar saudável. O processo de carga concluiu com código zero; não houve reset de volumes ou reinserção de documentos.

## 5. Busca vetorial validada

A CLI `scripts/buscar_embeddings_sprint4.py` codifica a consulta com o mesmo modelo/revisão e usa distância cosseno `<=>` no PostgreSQL. Filtros de ano e origem são aplicados antes do top-k; o resultado inclui IDs, texto, distância/similaridade e proveniência documental.

- **8/8 autocorrespondências por vetor** e **8/8 por texto recodificado pelo GTE** recuperaram o próprio ID no top-5 com distância próxima de zero.
- **9 consultas textuais** executadas, cobrindo temas, anos e origens; filtros corretos em todas as ocorrências retornadas.
- Mediana SQL: **177,5 ms**.
- Percentil 95 observado: **1,166 s**.
- Decisão: **manter busca exata**; atende ao alvo exploratório de mediana ≤ 5 s. HNSW não foi necessário nem criado.
- Smoke real da CLI aprovado com JSON UTF-8, acentos, top-1 e filtro 2025.

Tempos medidos localmente em 25 consultas SQL, incluindo autocorrespondências vetoriais/textuais e temas/filtros; não representam SLA. A inicialização do modelo não integra a latência SQL. O filtro `original` retorna vazio porque a origem desses documentos continua não homologada; `ficha_sintetica` e `nao_confirmada` funcionam conforme os registros existentes.

## 6. Testes e implementações

**96 testes aprovados** em **6,80 s**, incluindo PostgreSQL descartável. Cobrem idempotência, falha após commit/checkpoint, rollback de lote, revisão ausente, bloqueio de outra carga, manifesto adulterado, conteúdo alterado, amostragem, fingerprints e filtros. A CLI também foi executada contra o banco operacional.

Principais entregas: orquestrador integral, manifesto congelado, checkpoints, dispositivo/precisão explícitos, auditoria antes/depois, comparação automática de fingerprints, recomputação estratificada e busca textual com proveniência. Corrigidos o nome do filtro `ficha_sintetica` e a verificação explícita de revisão nula. Fluxo Spec Kit registrado na feature 009, com continuidade das features 007/008.

## 7. Alcance científico e continuidade

O aceite é técnico: vetorização integral, integridade, retomada e busca funcionando. Similaridade não é probabilidade de risco nem evidência suficiente de uma causa. As consultas temáticas não constituem nova avaliação humana de precisão/recall.

Permanecem para a etapa metodológica posterior: adjudicação humana dos pacotes assistidos da feature 007, confirmação de proveniência original e validação de relevância causal. Dados de 2026 continuam separados por proveniência e não se tornam evidência histórica de 2025. Random Forest é candidato a classificador supervisionado posterior, dependente de rótulos homologados; não foi treinado nesta sprint.

## 8. Evidências locais

- `logs/sprint4_009_baseline_gpu.json` — baseline e reprodução dos 157 vetores.
- `logs/sprint4_009_resumo_primeira_carga.json` — contagem de gerados/reutilizados e IDs de reuso.
- `logs/sprint4_corpus_20260923_202500_489043_primeira_execucao.json` — snapshot da primeira execução.
- `logs/sprint4_corpus_20260923_202500_489043.json` — configuração congelada, partes e retomada.
- `logs/sprint4_009_final_cpu.json` — auditoria integral, comparação com baseline e recomputação de 64 conteúdos.
- `logs/sprint4_009_cobertura_final.json` — cobertura por ano/origem, rótulos e tamanhos.
- `logs/sprint4_009_busca_final_textual.json` — rankings, proveniência, autocorrespondências e latências.
- `logs/sprint4_009_cli_smoke.json` — execução real da CLI.

Os logs operacionais e o corpus permanecem locais e ignorados pelo Git.

- `logs/sprint4_009_regressao_final.txt` — saída completa da regressão final de 96 testes.

## 9. Aceite Spec Kit
As 15 tarefas da feature 009 estão concluídas. A primeira convergência identificou a necessidade de testar autocorrespondência por entrada textual; T015 foi implementada e aprovada. A convergência final não encontrou lacunas acionáveis nos 7 requisitos, 5 critérios de sucesso, 3 histórias e 4 princípios constitucionais. O objetivo técnico da Sprint 4 foi atingido, com as limitações metodológicas acima preservadas.
