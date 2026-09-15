#!/bin/bash
# Executado pelo entrypoint apenas na inicializacao de um volume vazio.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=app_password="$TCC_APP_PASSWORD" <<'SQL'
CREATE ROLE tcc_app LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA tcc AUTHORIZATION tcc_app;
ALTER ROLE tcc_app SET search_path = tcc, public;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
