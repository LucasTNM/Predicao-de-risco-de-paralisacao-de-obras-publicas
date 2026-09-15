# Implementation Plan: Carga Documental 2025 e Auditoria 2026

## Arquitetura e Estratégia de Execução

1. **Separação de Processos:**
   - Processo A: Carga transacional de 2025 executada pelo `run_load.py` / `main.py` com commits atômicos por documento.
   - Processo B: Preflight de 2026 em processo independente assíncrono em modo `dry_run=True`.

2. **Garantias Transacionais:**
   - Para cada documento:
     - Criação/recuperação do registro em `dim_documento`.
     - Fragmentação sliding window (BERTimbau cased, 450 tokens, 50 overlap).
     - Deduplicação determinística por `chave_conteudo` (hash SHA-256) em `dim_embedding`.
     - Inserção dos registros na tabela `ponte_documento_embedding`.
     - Commit da transação por documento.

3. **Checkpoints e Progresso:**
   - Relatórios JSON salvos atomicamente a cada 100 documentos em `logs/sprint3_<tag>.json`.
   - Em caso de interrupção, o mecanismo de idempotência reusa documentos já carregados (`reutilizado`) sem duplicações.

4. **Validação Pós-Carga:**
   - Execução de `src/database/validation.py` (`validate_data`) em modo somente leitura.
   - Verificação de que `valido == True` e todas as inconsistências são `0`.
