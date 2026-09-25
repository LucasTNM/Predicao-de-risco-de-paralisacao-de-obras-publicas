# Pesquisa: primeiro piloto de embeddings

## Decisão 1: candidato de 768 dimensões

`intfloat/multilingual-e5-base` @ `d128750597153bb5987e10b1c3493a34e5a4502a` foi o candidato inicial: 768 dimensões, licença MIT e prefixos `passage: ` / `query: `. A auditoria integral encontrou 249 excedentes e reprovou seu uso para todo o corpus sem migração. [Modelo](https://huggingface.co/intfloat/multilingual-e5-base), [pooling](https://huggingface.co/intfloat/multilingual-e5-base/blob/main/1_Pooling/config.json).

## Decisão 2: auditar tokens efetivos

O E5 limita a entrada a 512 tokens; 450 WordPieces BERTimbau não garantem esse limite com o tokenizer XLM-R e o prefixo. A auditoria de 185.789 linhas registrou 249 excedentes, até 4.582 tokens. [Configuração do E5](https://huggingface.co/intfloat/multilingual-e5-base/blob/main/sentence_bert_config.json).

## Decisão 2a: alternativa de contexto longo

`Alibaba-NLP/gte-multilingual-base` @ `9bbca17d9273fd0d03d5725c7a4b0f6b45142062` tem 768 dimensões, licença Apache-2.0 e limite documentado de 8.192 tokens; em 185.789 linhas houve zero excedentes, máximo 4.580. Não usa prefixo adicional no exemplo oficial de geração. O modelo depende de código de `Alibaba-NLP/new-impl`, revisão a fixar `40ced75c3017eb27626c9d4ea981bde21a2662f4`; revisar esse código antes de ativar `trust_remote_code`. [Cartão GTE](https://huggingface.co/Alibaba-NLP/gte-multilingual-base).

## Decisão 3: ambiente isolado

O ambiente atual usa `transformers` 4.57.6. A instalação atual do `sentence-transformers` recomenda dependências mais novas; validar em ambiente separado antes de trocar a `.venv`. PyTorch declara suporte a Windows/Python 3.14. [Instalação Sentence Transformers](https://sbert.net/docs/installation.html), [PyTorch Windows](https://pytorch.org/get-started/locally/).

## Decisão 4: índice depois da carga

Começar com busca exata e medir. Se aprovado, usar HNSW cosseno com operador `<=>` e `vector_cosine_ops`, medindo recall/custo. Vetores nulos não entram no índice cosseno. [pgvector](https://github.com/pgvector/pgvector).

Alternativas de 768 dimensões como `paraphrase-multilingual-mpnet-base-v2` limitam entrada a 128 tokens. [MPNet](https://huggingface.co/sentence-transformers/paraphrase-multilingual-mpnet-base-v2).
