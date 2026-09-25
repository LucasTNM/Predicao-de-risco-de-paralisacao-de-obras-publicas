# Especificação: Primeiro piloto de embeddings (Sprint 4, Card 8)

**Data:** 2026-09-16. **Escopo:** decidir, com evidência, se um modelo de embeddings pode representar os fragmentos já carregados sem perda de texto e iniciar um piloto rastreável.

## Cenários

1. Como pesquisador, quero saber se todos os fragmentos cabem na janela do modelo proposto, para evitar truncamento silencioso.
2. Quero gerar vetores de uma amostra representativa e armazená-los com proveniência, podendo interromper e retomar sem duplicação.
3. Quero avaliar recuperação e custo antes de vetorizar o corpus inteiro.

## Requisitos

- **FR-001:** Auditar integralmente os fragmentos únicos com o tokenizer efetivo do modelo, incluindo instrução/prefixo e tokens especiais.
- **FR-002:** Rejeitar truncamento, vetor não finito, dimensão incorreta, norma zero e alteração do fragmento após leitura.
- **FR-003:** Fixar modelo/revisão/versões e registrar parâmetros de geração; gravar vetor e proveniência em uma transação por lote pequeno.
- **FR-004:** Permitir retomada idempotente, sem sobrescrever vetores incompatíveis.
- **FR-005:** Preservar documentos, ponte, offsets, fatos e rótulos; não promover dados de 2026 a evidência histórica.
- **FR-006:** Medir vazão, memória, espaço e qualidade de busca em amostra revisada antes de decidir sobre escala e índice.

## Critérios de sucesso

- **SC-001:** 100% dos fragmentos únicos têm comprimento contabilizado; nenhum excedente é truncado silenciosamente.
- **SC-002:** Piloto reproduzível com vetores válidos, rastreabilidade de revisão e reexecução sem duplicação.
- **SC-003:** Integridade relacional mantém zero inconsistências e rótulos permanecem nulos.
- **SC-004:** Existe relatório de custo e avaliação semântica que sustenta uma decisão explícita de prosseguir, trocar modelo ou migrar chunking.

## Fora do escopo da primeira etapa

Carga vetorial integral, índice HNSW definitivo, RAG, classificação, fine-tuning e mudança automática da fragmentação. O piloto pode ser interrompido por um gate reprovado sem comprometer a Sprint 3.
