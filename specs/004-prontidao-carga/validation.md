# Preparação da carga — 2026-09-15

## Estado

Auditoria física integral em execução. Este documento ainda não homologa o corpus.
Nenhuma carga operacional autorizada ou executada nesta etapa.

## Spec Kit e escopo

Fluxo aplicado: specify -> plan (pesquisa independente) -> tasks -> implement.
Checklist de requisitos: 7 critérios, 7 satisfeitos, 0 pendentes.
Constituição 1.0.0 preservada; não alterar DDL, 450/50 ou alvo científico.

## Correções e testes já executados

- Relatório publicado no início e durante progresso; anos concluídos preservados.
- Inventário anual por PDF/TXT, obra e hashes; fingerprint das quatro fontes tabulares
  antes/depois. Alteração de fonte bloqueia continuação antes da conexão ao banco.
- Parecer de prontidão separado do estado PREFLIGHT; quarentena não vira aprovação.
- Ordem documental corrigida para preflight -> carga de documentos/chunks -> embeddings.
- Help dos anos corrigido; validar-banco abre conexão somente leitura; CLI sinaliza
  parecer bloqueado com código 2.
- Quatro cenários novos falharam antes das correções (3 testes anteriores aprovados).
- Testes focados: **20 passed** (chunker, preflight e relatórios).
- Regressão e PostgreSQL descartável: **53 passed**, 6,65 s, via scripts/testar_sprint3.py.
- Revisão adicional: teste de quarentena agora inclui documento elegível, distinguindo
  bloqueio por quarentena de ausência de documentos; exclusões são testadas separadamente.
- Carga futura bloqueia antes de conectar se há quarentenas, salvo opção explícita
  --excluir-quarentena, que mantém essas fontes fora. Dois cenários falharam antes
  dessa proteção; regressão final após a mudança: **56 passed**, 5,89 s.
- pip check: sem dependências quebradas.
- .env, planilhas, logs e feature.json continuam ignorados; nenhum desses arquivos
  foi incluído no conjunto versionável.

## Banco operacional antes da auditoria

Conexão read_only=True; nove verificações sem inconsistências. Contagens:
28.288 obras, 28.288 fatos, 45 documentos, 205 fragmentos, 207 vínculos.
Baseline e timestamps registrados em logs/prontidao_20260915_banco_antes.json.

## Execução integral

Relatório em logs/sprint3_20260915_181902_571640.json; console em
logs/prontidao_20260915_console.log. Execução sem ano/base/limite, dry_run=True,
com guarda adicional que proíbe abertura de conexão pelo carregador.
Inventários detalhados permanecem em logs/; não versionar corpus ou metadados
operacionais por arquivo. O parecer final será registrado após o término.

A execução integral já estava em andamento quando foi acrescentada a guarda de
carga futura. Ela usa a revisão identificada em codigo_sha256 no próprio relatório;
o algoritmo de preflight não mudou. A guarda adicional de conexão e dry_run=True
protegem a auditoria em andamento; não houve necessidade de reler o corpus por essa
mudança exclusivamente no fluxo de escrita futura.

## Limites científicos

Elegibilidade para armazenamento não homologa treino. Fichas sintéticas continuam
distintas de originais; origem não confirmada não vira original por inferência.
Snapshots 2026 não substituem alvo histórico 2025. Labels/vetores permanecem NULL.
Na carga futura, revalidar fontes; relatório anterior não dispensa leitura física.
