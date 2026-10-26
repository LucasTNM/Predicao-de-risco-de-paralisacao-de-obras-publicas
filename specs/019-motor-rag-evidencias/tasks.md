# Tasks: Motor de Busca RAG por Obra (Sprint 7)

**Feature**: `019-motor-rag-evidencias`  
**Status**: Concluído e auditado em 2026-10-19 — 8/8 tarefas finalizadas com sucesso.

## Phase 1: Setup e Consultas Causais
- [x] T001 Implementar `src/rag/queries.py` com as 4 consultas causais (Regular, Técnica, Orçamentária e Abandono), codificação GTE e auditoria estrita de termos proibidos (sem "paralisad", "em execu").
- [x] T002 Implementar testes unitários em `tests/test_rag.py` validando que as consultas causais não contêm termos de situação e que o validador recusa violações.

## Phase 2: User Story 1 — Motor de Recuperação por Obra (P1)
- [x] T003 [US1] Implementar `src/rag/retriever.py` com `WorkEvidenceRetriever` executando busca cosseno exata restrita à obra consultada, com expurgo de fichas sintéticas e extração de proveniência completa.
- [x] T004 [US1] Adicionar testes unitários em `tests/test_rag.py` para retorno de chunks com documento, offsets e desempate determinístico, além de retorno limpo (`sem_evidencia_textual = True`) para obras sem documentos.

## Phase 3: User Story 2 & 3 — Lotes Congelados e Materialização (P1/P2)
- [x] T005 [US2/US3] Implementar `src/rag/materializer.py` e script CLI `scripts/gerar_evidencias_rag.py` para processar as partições de treino_dev e teste_retido com deduplicação de chunks e ordenação por similaridade.
- [x] T006 [US3] Executar `scripts/gerar_evidencias_rag.py` e gravar os lotes congelados `evidencias_rag_dev.jsonl` e `evidencias_rag_teste.jsonl` em `dados_processados/sprint7/` com manifesto auditável SHA-256.

## Phase 4: Diagnóstico de Cobertura e Conclusão (P2)
- [x] T007 [US3] Redigir `specs/019-motor-rag-evidencias/report.md` com a tabela de cobertura por classe, análise de suficiência amostral para o BERTimbau e inspeção de 30 obras.
- [x] T008 Executar suíte completa de testes (`pytest tests/test_rag.py`) e runner `scripts/testar_sprint3.py` para homologação da feature.

## Dependencies
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008.
