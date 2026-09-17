# Plano: Carga documental de 2026

## Contexto técnico

CLI Python em `src/main.py` e `src/database/run_load.py`; PostgreSQL 17/pgvector; fontes no Drive; esquema existente de cinco tabelas; BERTimbau cased, janelas 450/50.

## Constituição

- I: proveniência de 2026 sem alterar alvo histórico ou atribuir rótulos.
- II: validação física e hashes; rejeições e ambiguidades fora do lote.
- III: observação por obra/data-base, ponte íntegra, vetores nulos.
- IV: relatório atômico, transação por documento, retomada idempotente, testes aprovados.

## Execução

1. Conferir carga de 2025 e baseline operacional em leitura.
2. Concluir preflight físico de 2026 e confrontar ocorrências com a destinação registrada.
3. Rodar regressão afetada, verificar esquema e executar `--modo carga --ano 2026 --excluir-quarentena` se o lote estiver apto.
4. Conferir resultado, contagens por ano e integridade em leitura; registrar evidências.

Nenhuma migração ou alteração de esquema. Identidades: obra `(base_de_dados,id_tcu,data_base)`; documento `(ano_base,base_origem,caminho_pdf_relativo)`.
