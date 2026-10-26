# Implementation Plan: 019-motor-rag-evidencias

**Branch**: `019-motor-rag-evidencias` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/019-motor-rag-evidencias/spec.md`

## Summary

Implementar o Motor de Busca RAG restrito por obra no PostgreSQL/pgvector. O motor recupera até $k$ fragmentos textuais mais relevantes com base em consultas causais pré-definidas (Aspecto Geral/Execução, Aspecto Técnico, Aspecto Orçamentário-Financeiro e Aspecto Contratual/Abandono), sem vazamento de termos de situação ("paralisada", "em execução"). O motor aplica estritamente a política de fontes autorizadas definida na Feature 018 (expurgo de fichas sintéticas, operando exclusivamente sobre documentos autênticos como relatórios e editais). O motor materializa os lotes de evidências para as partições `treino_dev` e `teste_retido` em arquivos imutáveis com manifesto auditável de hashes SHA-256 e relatório de cobertura textual.

## Technical Context

**Language/Version**: Python 3.14 (`.venv` para consultas e geração de lotes; modelo GTE de embeddings da Sprint 4 para vetorizar as consultas).

**Primary Dependencies**: `psycopg` (ou conexão `src.database.connection`), `pgvector`, `sentence-transformers` (para codificação de queries com GTE Multilingual), `pandas`, `duckdb`.

**Storage**: PostgreSQL com extensão `vector` no schema `tcc` (somente leitura); lotes materializados em `dados_processados/sprint7/` (`evidencias_rag_dev.jsonl`, `evidencias_rag_teste.jsonl`) com manifesto SHA-256.

**Testing**: `pytest` em `tests/test_rag.py` (unitários de validação de consultas sem termos proibidos, restrição determinística por obra, ordenação cosseno exata, deduplicação de chunks e retorno limpo em obras sem documentos).

**Target Platform**: Windows 11 local, PostgreSQL 16 com pgvector no Docker Desktop.

**Project Type**: Módulo Python de recuperação semântica (`src/rag/`) e script CLI de materialização em lote (`scripts/gerar_evidencias_rag.py`).

**Performance Goals**: Recuperação por obra em lote com throughput de $\ge 50$ obras/s para materializar as 14.522 obras de dev e 3.632 obras de teste em poucos minutos.

**Constraints**:
- Acesso ao banco estritamente em `read_only = True`.
- Proibição de busca aproximada (HNSW); uso de distância cosseno exata `<=>`.
- Restrição inviolável à própria obra: zero contaminação cruzada entre obras.
- Proibição absoluta de termos da situação da obra nas consultas causais (Artigo I da Constituição).
- Proibição de fichas sintéticas (`origem_documento != 'ficha_sintetica'`).

## Constitution Check

| Princípio | Exigência | Situação no desenho |
| :--- | :--- | :---: |
| I. Fidedignidade e rótulo real | Nenhuma evidência textual deve conter a situação vazada da obra | PASS: consultas causais auditadas sem termos de situação; fichas sintéticas expurgadas |
| II. Integridade semântica | Fragmentos preservam o texto nativo e proveniência (documento, offsets) | PASS: o motor retorna `conteudo_chunk`, `char_inicio`, `char_fim`, `id_documento` |
| III. Consistência relacional | Obras sem documentos recebem flag explícita `sem_evidencia_textual` sem inventar texto | PASS: retorno vazio para obras sem documentos autênticos |
| IV. Reprodutibilidade | Consultas versionadas com hash; semente fixada; lotes congelados com manifesto SHA-256 | PASS: `consultas_causais.json` com hash; lotes salvos em JSONL imutáveis |

## Project Structure

### Documentation (this feature)

```text
specs/019-motor-rag-evidencias/
├── spec.md
├── plan.md
├── tasks.md
├── checklists/requirements.md
└── report.md                  # Relatório de cobertura e suficiência de evidências
```

### Source Code

```text
src/rag/
├── __init__.py
├── queries.py                 # Definição e auditoria das 4 consultas causais sem termos de situação
├── retriever.py               # Motor de recuperação SQL com pgvector restrito por obra
└── materializer.py            # Orquestrador de lote para treino_dev e teste_retido com deduplicação

scripts/
└── gerar_evidencias_rag.py    # Script CLI para materializar lotes congelados e calcular métricas

tests/
└── test_rag.py                # Suíte de testes unitários do motor e das consultas
```

## Decisões Técnicas

1. **Definição das Consultas Causais**:
   - As 4 consultas representam os eixos analíticos de auditoria pública sem revelar situação:
     - `Causal_Regular`: "execução regular do objeto, cronograma físico-financeiro dentro do prazo previsto, cumprimento das etapas contratuais e metas acordadas"
     - `Causal_Tecnica`: "deficiência de projeto executivo, falhas de engenharia, divergências geotécnicas, necessidade de revisão de traçado, inconformidades técnicas estruturais"
     - `Causal_Orcamentaria`: "indisponibilidade orçamentária, contingenciamento de recursos, atraso na liberação de empenho e repasse financeiro, contrapartida municipal ou estadual pendente"
     - `Causal_Abandono`: "descumprimento de cláusulas contratuais pela empresa contratada, desmobilização injustificada de máquinas e canteiro de obras, rescisão unilateral, abandono e aplicação de sanções administrativas"
   - As consultas são pré-codificadas com o modelo GTE Multilingual da Sprint 4 e armazenadas em `src/rag/consultas_causais.json`.
2. **Estratégia de Recuperação Otimizada por Obra**:
   - Como obras sem documentos representam ~98,8% da Classe 1 e ~58% da Classe 0, o retriever consulta previamente o conjunto de obras que possuem documentos autênticos válidos em 2025.
   - Para as obras com documentos autênticos, executa-se a busca dos chunks vinculados à obra calculando a similaridade cosseno exata contra os 4 vetores de consulta, ordenando por menor distância e selecionando os top-$k$ chunks deduplicados.
   - Para as obras sem documentos autênticos, gera-se deterministicamente o registro vazio com `sem_evidencia_textual = True`, eliminando overhead de consulta.
3. **Deduplicação de Chunks por Obra**:
   - Se o mesmo chunk for o mais próximo para duas consultas distintas da mesma obra, ele é retornado uma única vez, preservando as consultas que o ativaram e permitindo preencher as vagas restantes do top-$k$ com outros fragmentos distintos.
