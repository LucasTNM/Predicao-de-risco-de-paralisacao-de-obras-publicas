-- Sprint 3: estrela com ponte multivalorada. Schema tcc provisionado no bootstrap.
-- Execucao direta: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f este_arquivo.sql
BEGIN;
SET LOCAL search_path TO tcc, public;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS dim_obra (
    id_obra bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    base_de_dados text NOT NULL CHECK (base_de_dados <> ''),
    id_tcu text NOT NULL CHECK (id_tcu <> ''),
    data_base date NOT NULL,
    ano_base integer NOT NULL CHECK (ano_base = EXTRACT(YEAR FROM data_base)),
    num_instrumento text,
    empreendimento text,
    situacao text,
    situacao_origem text,
    local_original text,
    uf text,
    municipio text,
    setor text,
    repassador text,
    obra_pac text,
    pacto text,
    fonte jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (base_de_dados, id_tcu, data_base),
    UNIQUE (id_obra, ano_base)
);

CREATE TABLE IF NOT EXISTS fato_risco (
    id_fato bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_obra bigint NOT NULL UNIQUE,
    ano_base integer NOT NULL,
    causa_paralisacao text,
    exec_fisica numeric,
    exec_financeira numeric,
    valor_investimento numeric,
    valor_desbloqueado numeric,
    label_risco smallint CHECK (label_risco BETWEEN 0 AND 3),
    origem_rotulo text,
    status_rotulagem text NOT NULL DEFAULT 'PENDENTE',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (id_obra, ano_base) REFERENCES dim_obra (id_obra, ano_base),
    UNIQUE (id_fato, ano_base),
    CHECK ((label_risco IS NULL AND status_rotulagem = 'PENDENTE') OR
           (label_risco IS NOT NULL AND status_rotulagem = 'ROTULADO' AND origem_rotulo IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS dim_documento (
    id_documento bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ano_base integer NOT NULL,
    base_origem text NOT NULL,
    base_coleta text NOT NULL,
    caminho_pdf_relativo text NOT NULL,
    caminho_txt_relativo text NOT NULL,
    sha256_pdf text NOT NULL CHECK (sha256_pdf ~ '^[0-9a-f]{64}$'),
    sha256_txt text NOT NULL CHECK (sha256_txt ~ '^[0-9a-f]{64}$'),
    tipo_documento text,
    origem_documento text NOT NULL CHECK (origem_documento IN ('original', 'ficha_sintetica', 'nao_confirmada')),
    metodo_extracao text,
    metodo_limpeza text,
    total_paginas integer NOT NULL CHECK (total_paginas >= 0),
    total_chars integer NOT NULL CHECK (total_chars > 0),
    score_sujeira numeric NOT NULL CHECK (score_sujeira BETWEEN 0 AND 1),
    chunk_config text NOT NULL CHECK (chunk_config ~ '^[0-9a-f]{64}$'),
    assinatura_carga text NOT NULL CHECK (assinatura_carga ~ '^[0-9a-f]{64}$'),
    num_chunks integer NOT NULL CHECK (num_chunks > 0),
    num_obras integer NOT NULL CHECK (num_obras > 0),
    metadados jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ano_base, base_origem, caminho_pdf_relativo),
    UNIQUE (id_documento, ano_base, chunk_config)
);

CREATE TABLE IF NOT EXISTS dim_embedding (
    id_embedding bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave_conteudo text NOT NULL UNIQUE CHECK (chave_conteudo ~ '^[0-9a-f]{64}$'),
    conteudo_chunk text NOT NULL CHECK (length(conteudo_chunk) > 0),
    token_ids integer[] NOT NULL,
    num_tokens integer NOT NULL CHECK (num_tokens BETWEEN 1 AND 510),
    tokenizer_name text NOT NULL,
    tokenizer_revision text NOT NULL,
    versao_chunking text NOT NULL,
    chunk_config text NOT NULL CHECK (chunk_config ~ '^[0-9a-f]{64}$'),
    embedding vector(768),
    modelo_embedding text,
    revisao_embedding text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (cardinality(token_ids) = num_tokens AND array_ndims(token_ids) = 1),
    CHECK (0 <= ALL(token_ids) AND array_position(token_ids, NULL) IS NULL),
    CHECK ((embedding IS NULL AND modelo_embedding IS NULL AND revisao_embedding IS NULL) OR
           (embedding IS NOT NULL AND modelo_embedding IS NOT NULL AND revisao_embedding IS NOT NULL)),
    UNIQUE (id_embedding, chunk_config)
);

CREATE TABLE IF NOT EXISTS ponte_documento_embedding (
    id_fato bigint NOT NULL,
    id_documento bigint NOT NULL,
    id_embedding bigint NOT NULL,
    ano_base integer NOT NULL,
    chunk_config text NOT NULL,
    posicao_chunk integer NOT NULL CHECK (posicao_chunk >= 0),
    token_inicio integer NOT NULL CHECK (token_inicio >= 0),
    token_fim integer NOT NULL CHECK (token_fim > token_inicio),
    char_inicio integer NOT NULL CHECK (char_inicio >= 0),
    char_fim integer NOT NULL CHECK (char_fim > char_inicio),
    PRIMARY KEY (id_fato, id_documento, chunk_config, posicao_chunk),
    FOREIGN KEY (id_fato, ano_base) REFERENCES fato_risco (id_fato, ano_base),
    FOREIGN KEY (id_documento, ano_base, chunk_config)
        REFERENCES dim_documento (id_documento, ano_base, chunk_config),
    FOREIGN KEY (id_embedding, chunk_config)
        REFERENCES dim_embedding (id_embedding, chunk_config)
);

CREATE INDEX IF NOT EXISTS idx_obra_ano_base ON dim_obra (ano_base, base_de_dados);
CREATE INDEX IF NOT EXISTS idx_fato_ano ON fato_risco (ano_base);
CREATE INDEX IF NOT EXISTS idx_ponte_documento ON ponte_documento_embedding (id_documento);
CREATE INDEX IF NOT EXISTS idx_ponte_embedding ON ponte_documento_embedding (id_embedding);

COMMENT ON TABLE dim_obra IS 'Cadastro da obra em uma data-base; IDs TCU preservados como texto.';
COMMENT ON TABLE fato_risco IS 'Uma observacao por obra/data-base. Agregar medidas antes de expandir pela ponte.';
COMMENT ON TABLE dim_documento IS 'Documento fisico por particao anual, sem pressupor uma unica obra.';
COMMENT ON TABLE dim_embedding IS 'Conteudo e IDs de tokens; vetor pendente ate o Card 8.';
COMMENT ON TABLE ponte_documento_embedding IS 'Ocorrencia documental por fato/chunk; offsets zero-based, fim exclusivo.';
COMMIT;
