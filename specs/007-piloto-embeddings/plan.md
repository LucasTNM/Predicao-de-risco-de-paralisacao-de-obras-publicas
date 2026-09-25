# Plano de implementação: Primeiro piloto de embeddings

**Branch:** `codex/prontidao-carga` | **Data:** 2026-09-16 | **Spec:** [spec.md](spec.md)

## Resumo

Executar os gates definidos em `planos/Sprint4_Plano_de_Implementacao.md`: auditoria integral de comprimento com tokenizer E5, piloto vetorial rastreável em PostgreSQL e avaliação de custo/qualidade antes de ampliar o lote.

## Contexto técnico

- Python 3.14.3 no Windows; ambiente da Sprint 3 fixa `transformers==4.57.6` e não contém PyTorch nem `sentence-transformers`.
- PostgreSQL 17 + pgvector 0.8.6; `tcc.dim_embedding` tem 185.789 linhas com `embedding vector(768) NULL`.
- E5 @ `d128750597153bb5987e10b1c3493a34e5a4502a` foi reprovado em 249 fragmentos acima de 512 tokens. GTE multilingual @ `9bbca17d9273fd0d03d5725c7a4b0f6b45142062` é o candidato de piloto: 768 dimensões, 8.192 tokens, zero excedentes em auditoria integral. Código remoto `Alibaba-NLP/new-impl` requer revisão e pinagem separada.
- Testes: script de regressão Sprint 3 e integração PostgreSQL isolada para o gravador; validação do banco operacional em leitura antes/depois.

## Constituição: gates

- I: vetores não alteram alvo, classes ou uso histórico de 2026.
- II: fragmentos canônicos e offsets permanecem intactos; nenhum truncamento silencioso.
- III: cinco tabelas e ponte preservadas; revisão do modelo registrada; 768 dimensões.
- IV: revisão/versões/manifestos fixos, escrita transacional, retomada e testes.

## Fases

1. **Pesquisa:** documentar seleção de modelo e risco de limite de tokens em [research.md](research.md).
2. **Auditoria em leitura:** E5 com prefixo `passage: ` e GTE sem prefixo; contar especiais, registrar excedentes e distribuição. Ambos concluídos em 185.789 linhas.
3. **Ambiente e piloto:** isolar dependências, testar inferência e persistência transacional em amostra determinística, preservando dados de 2025/2026.
4. **Avaliação:** medir recursos, consultas relevantes e plano de busca; decidir escala/índice. Sem aprovação automática da carga integral.

## Estrutura

- `scripts/auditar_tokens_sprint4.py`: gate de comprimento sem escrita no banco.
- `src/database/`: módulo futuro de geração/gravação de vetores, separado do carregador documental.
- `tests/`: testes de contrato de comprimento e persistência com PostgreSQL isolado.
- `specs/007-piloto-embeddings/`: decisão, contratos, tarefas e validação.

## Continuação em 2026-09-19

Implementar T009 com busca cosseno exata em `src/database/vector_search.py`,
contrato compartilhado de inferência sem truncamento em `src/embedding_model.py`
e CLI `scripts/avaliar_busca_sprint4.py`. Filtrar ano/origem e modelo/revisão antes
de selecionar top-k, evitando multiplicação pela ponte. Gerar pacote local para
julgamento humano com assinatura do universo e aceitar métricas somente depois
da revisão. Separar avaliação técnica da homologação semântica.

Ampliar piloto determinístico para oito conteúdos por estrato (limite de 16),
medir RSS/pico de working set, inferência e armazenamento. Projeção linear dessa
amostra é exploratória e não homologa duração da carga integral. Manter busca
exata enquanto não houver evidência de necessidade de HNSW.

Registrar a investigação solicitada de Random Forest em `random-forest.md`.
Treinamento continua fora deste piloto; não criar rótulos a partir dos vetores.

## Execução das pendências de convergência

T012: `scripts/benchmark_embeddings_sprint4.py` audita todos os comprimentos GTE
e seleciona até oito chunks por faixa, pelos menores SHA-256 de ID/chave, sem
dependência da ordem de leitura. Três repetições por faixa, batch 2, CPU, aquecimento
separado. Projetar pela população de cada faixa, sem apresentar min/max como IC.
Inspecionar PGDATA e volume Docker e registrar também o espaço do host que sustenta
o VHDX. Reserva 4x do payload vetorial é hipótese de planejamento, não medição de WAL.

T011: por solicitação do usuário, usar os pacotes existentes para revisão assistida.
Identificar `tipo_revisao=assistida_ia` e autoria Codex; manter separados os estados
de avaliação assistida e humana. Julgar texto completo, incluindo negativos,
preservando a assinatura do universo. Homologação humana não é inferida dessa execução.
Comparar `nao_confirmada` com o conjunto misto sem converter origem em `original`.
