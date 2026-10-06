# Contrato CLI
preparar: transação PostgreSQL somente leitura, criar população/manifesto/auditoria local, recusar substituição divergente.
coletar: usar manifesto, até duas fontes oficiais por caso, cache com SHA256 e retomada; retornar resultados também para bloqueios de rede, nunca inventar ausência causal.
relatar: consolidar contagens por coorte/base, decisão de escala, revisão de catálogo e dataset auxiliar, rótulos originais preservados.
Identidade PNCP: chave oficial de controle tem CNPJ, espécie1 compra/2 contrato, sequência e ano. Número do instrumento não é chave; sem chave oficial verificada retorna vazio com motivo. Antes de arquivos conferir campos oficiais contra instituição/instrumento/objeto. Compra não prova contrato.

Resultados incluem manifesto_sha256 e implementacao_sha256. Reprocessamento explícito preserva resultado anterior; cache fonte sempre verificado. Revisões de identidade não escrevem rótulos. Tempos reportados são de processamento, não revisão manual, que não foi cronometrada.
