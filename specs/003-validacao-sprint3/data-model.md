# Contrato de dados preservado

| Entidade | Identidade / relações | Invariantes |
| --- | --- | --- |
| dim_obra | base, ID textual, data-base | uma linha por snapshot; ano coerente |
| fato_risco | única por id_obra | medidas numeric, label NULL/PENDENTE |
| dim_documento | ano, base, caminho PDF | SHA-256 PDF/TXT, configuração, contagens positivas |
| dim_embedding | hash de texto, IDs e configuração | 1–510 tokens, vetor e metadados NULL nesta sprint |
| ponte_documento_embedding | fato, documento, configuração, posição | ano consistente, offsets zero-based/fim exclusivo |

Nenhuma alteração de DDL prevista. A validação aplicacional reforça comparação
dos vínculos reais, hash canônico dos chunks e continuidade dos intervalos.

Preflight: manifesto → excluído/quarentena ou documento elegível com hashes
observados. Carga: elegível → carregado/reutilizado, ou falha com rollback.
Mudança de fonte após preflight invalida a auditoria, inclusive com `--force`;
é necessário novo preflight. Force permite substituir uma carga anterior
quando as fontes atuais foram validadas.
