# Decisões de preparação

## Relatório de prontidão
Decision: enriquecer o relatório existente com progresso parcial, inventário
por documento, hashes das quatro fontes anuais e instante final.
Rationale: PREFLIGHT é término de auditoria, não aprovação; contagens sozinhas
não identificam o conjunto elegível. A pesquisa independente via agente do
speckit-plan confirmou essas lacunas (run_load.py/preflight.py).
Alternatives: reaproveitar só o relatório histórico foi rejeitado; parar no piloto
não responde ao pedido. Não usar hashes antigos como substituto da leitura física.

## Destinação conservadora
Decision: excluir rejeitados e manter quarentenados fora do lote, com evidência
individual e condição de reentrada; só corrigir origem/vínculo com comprovação.
Rationale: artigo II; sucesso de higienização não revoga rejeição de coleta.
Alternatives: aprovar por nome do arquivo ou apagar o problema violaria proveniência.

## Escopo e evolução
Decision: preservar DDL/450-50 e ordem preflight -> carga -> embeddings.
Rationale: já verificados no piloto, vetores NULL são parte do contrato atual.
Treino, múltiplos snapshots intra-ano e busca vetorial permanecem etapas futuras.

## Investigação das quarentenas conhecidas

Pesquisa somente leitura de 2026-09-15: os três vínculos múltiplos SIMEC não são
compartilhamentos N:N homologáveis. Conteúdo/localidade/objeto dos documentos
divergem das escolas indicadas nos registros. Manter fora; possível colisão entre
identificadores de sistemas é hipótese, não causa comprovada.

As 23 coletas ausentes não foram localizadas nos manifestos atuais de 2025/2026,
inclusive com normalização de nomes. Uma é duplicata física por SHA-256 de arquivos
com coleta registrada; as outras 22 continuam sem proveniência suficiente.

O texto de qualidade residual tem score 0,983330, 65.507 caracteres, extração nativa
de 23 páginas e falha registrada da camada LLM. Inspeção mostra glifos privados.
Reentrada exige reextração/OCR e validação sem alterar artificialmente a métrica.

Nenhuma dessas 27 fontes foi promovida. Evidências individuais, nomes, linhas dos
manifestos e hashes ficam no relatório operacional local de destinação em logs/.
Os números atuais finais dependem do preflight físico integral ainda em execução.
