# Carga documental de 2026

**Data**: 2026-09-16. **Escopo**: conferir a carga existente, concluir o preflight de 2026 e carregar somente o lote elegível.

## Cenários e aceite

1. Como pesquisador, quero um preflight integral e atual com hashes, contagens e destinação de cada ocorrência. Uma execução parcial não aprova o corpus.
2. Como pesquisador, quero persistir os documentos elegíveis de 2026, seus fragmentos e vínculos de forma transacional e idempotente, mantendo fora as quarentenas.
3. Após a carga, quero verificar que 2025 foi preservado, que vetores e rótulos seguem nulos e que a integridade relacional está válida.

## Requisitos

- **FR-001**: Auditar fisicamente 100% dos candidatos de 2026 e registrar estabilidade das fontes.
- **FR-002**: Conferir baseline do banco e carga de 2025 antes de qualquer escrita.
- **FR-003**: Excluir explicitamente do lote cada fonte rejeitada ou ambígua, sem promovê-la por inferência.
- **FR-004**: Persistir documento, chunks e ponte atomicamente; retomada não duplica dados.
- **FR-005**: Preservar rótulo histórico e deixar embeddings e labels nulos.
- **FR-006**: Validar integridade, contagens por ano, falhas e proveniência após a carga.

## Critérios de sucesso

- **SC-001**: Preflight integral concluído, com toda ocorrência destinada.
- **SC-002**: Todos os elegíveis carregados ou reutilizados, com zero falhas; nenhum excluído persistido.
- **SC-003**: `valido: true` e zero inconsistências em todas as métricas.
- **SC-004**: Contagens e dados de 2025 preservados; vetores e rótulos nulos.

## Limites

O checkpoint anterior em 34.000/35.602 arquivos não é aprovação. A carga não inclui embeddings, treinamento nem reclassificação. Armazenar 2026 não autoriza usá-lo como evidência histórica.
