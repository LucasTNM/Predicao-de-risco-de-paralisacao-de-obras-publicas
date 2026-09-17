# Preparação da carga — 2026-09-15

> **Atualização de 2026-09-16:** as contagens e o estado sem carga abaixo
> descrevem esta etapa histórica. A carga elegível de 2025 e 2026 foi executada
> depois; os resultados atuais estão em `specs/005-carga-documental-2025/validation.md`
> e `specs/006-carga-documental-2026/validation.md`. As exclusões continuam
> rastreadas e não foram promovidas automaticamente.

## Estado final

**Preflight integral concluído em 2026-09-15. STATUS: `PREFLIGHT`. PRONTIDÃO: `APTO_COM_EXCLUSOES`.**
Nenhuma carga operacional autorizada ou executada nesta etapa.
Nenhuma mutação no banco operacional ou nas fontes de corpus.

## Spec Kit e escopo

Fluxo aplicado: specify → plan (pesquisa independente) → tasks → implement.
Checklist de requisitos: 7 critérios, 7 satisfeitos, 0 pendentes.
Constituição 1.0.0 preservada; não alterar DDL, 450/50 ou alvo científico.

## Correções e testes executados

- Relatório publicado no início e durante progresso; anos concluídos preservados.
- Inventário anual por PDF/TXT, obra e hashes; fingerprint das quatro fontes tabulares
  antes/depois. Alteração de fonte bloqueia continuação antes da conexão ao banco.
- Parecer de prontidão separado do estado PREFLIGHT; quarentena não vira aprovação.
- Ordem documental corrigida para preflight → carga de documentos/chunks → embeddings.
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

## Banco operacional antes e depois da auditoria

Verificação em read_only=True; nove verificações sem inconsistências.
Contagens idênticas antes e depois: 28.288 obras, 28.288 fatos, 45 documentos,
205 fragmentos, 207 vínculos. Baseline em logs/prontidao_20260915_banco_antes.json.
Timestamps de última escrita inalterados (2026-09-10 02:22 UTC).
**Banco operacional preservado integralmente (FR-002, SC-002).**

## Execução integral do preflight (T005)

Duas execuções independentes confirmaram os mesmos resultados:
- Relatórios: logs/sprint3_20260915_183441_249434.json e logs/sprint3_20260915_183619_322876.json
- Resumo definitivo: logs/prontidao_20260915_resumo_definitivo.json
- dry_run=True em ambas; guarda adicional proíbe abertura de conexão.

### Resultados por ano

| Ano  | Manifestados | Elegíveis | Excluídos | Prontidão            |
|------|-------------|-----------|-----------|----------------------|
| 2025 | 15.408      | 15.381    | 27        | APTO_COM_EXCLUSOES   |
| 2026 | 3.048       | 3.021     | 27        | APTO_COM_EXCLUSOES   |
| **Total** | **18.456** | **18.402** | **54** | **APTO_COM_EXCLUSOES** |

### Ocorrências por ano

**2025 (27 ocorrências):**
- `txt_ausente`: 1 — arquivo de texto não encontrado no corpus físico
- `extracao_nao_univoca_ou_nao_ok`: 2 — extração sem resultado único aceitável
- `coleta_nao_aceita`: 24 — status de validação da coleta fora de {VALIDADO, VALIDADO_COM_RESSALVAS}

**2026 (27 ocorrências):**
- `vinculo_multiplo_nao_homologado`: 3 — documento candidato a mais de uma obra (investigados, ver seção abaixo)
- `coleta_nao_aceita`: 24 — mesmo critério de 2025

Fontes tabulares estáveis durante toda a auditoria (fingerprint antes = depois, ambos os anos).

## Destinação das pendências (T006/T007)

Investigação das 27 quarentenas históricas concluída.
Arquivo completo: logs/prontidao_20260915_evidencias_quarentenas.json
**Todas com decisão: `MANTER_FORA_DO_LOTE`.**

### Vínculos múltiplos SIMEC (2026) — 3 documentos investigados individualmente

| Documento | Obras candidatas | Diagnóstico | Evidência |
|-----------|-----------------|-------------|-----------|
| SIMEC_700261_1_CONIC...Baixa.txt | SIMEC-5679 / SIMEC-5680 | CONTEUDO_INCOMPATIVEL_COM_OBRAS | Texto trata de Convenio "CARA E CULTURA NEGRA" — objeto incompatível com ambas as obras candidatas (escolas AM) |
| SIMEC_806021_1_806021__Aprovacao...txt | SIMEC-5711 / SIMEC-5712 | CONTEUDO_INCOMPATIVEL_COM_OBRAS | Texto trata de Patrulha Mecanizada em Itaguaçu-ES; obras manifestadas são escolas em Atalaia do Norte-AM |
| SIMEC_806049_1_1018_250_57...txt | SIMEC-6729 / SIMEC-6757 | CONTEUDO_INCOMPATIVEL_COM_OBRAS | Texto trata de Microdrenagem do Anel Viário de Jaboticabal-SP; obras manifestadas são escolas em Estreito-MA e Arari-MA |

**Condição de reentrada:** Documento correto da obra ou vínculo comprovado com observação existente
e proveniência; não homologar N:N pela coincidência de identificador.

### Documentos CAIXA sem coleta aceita (24 em cada ano)

Documentos sem validação da coleta (`VALIDADO` ou `VALIDADO_COM_RESSALVAS`).
Destinação: `MANTER_FORA_DO_LOTE`. Condição de reentrada: nova coleta com validação aprovada.

### 1 documento CAIXA com TXT ausente (2025)

Arquivo de texto não encontrado no corpus físico. Destinação: `MANTER_FORA_DO_LOTE`.
Condição de reentrada: reextração/OCR e higienização confirmadas.

### 2 documentos com extração não OK (2025)

Extração não produziu resultado único aceitável. Destinação: `MANTER_FORA_DO_LOTE`.
Condição de reentrada: reextração com status OK ou OCR_PARCIAL univocamente vinculado.

## Conferência do banco após auditoria (T010)

Verificação read_only=True realizada após conclusão do preflight:
- dim_obra: 28.288 ✅ (= baseline)
- fato_risco: 28.288 ✅ (= baseline)
- dim_documento: 45 ✅ (= baseline)
- dim_embedding: 205 ✅ (= baseline)
- ponte_documento_embedding: 207 ✅ (= baseline)
- Todas as inconsistências: 0 ✅
- transaction_read_only: on ✅

**Banco operacional íntegro e inalterado. SC-002 satisfeito.**

## Limites científicos

Elegibilidade para armazenamento não homologa treino. Fichas sintéticas continuam
distintas de originais; origem não confirmada não vira original por inferência.
Snapshots 2026 não substituem alvo histórico 2025. Labels/vetores permanecem NULL.
Na carga futura, revalidar fontes; relatório anterior não dispensa leitura física.

## Cobertura Spec Kit — speckit-converge (T011)

Executado em 2026-09-15. Resultado: **✅ Converged**.

| Categoria | Itens verificados | Gaps |
|-----------|-------------------|------|
| Requisitos funcionais (FR-001..FR-006) | 6 | 0 |
| Critérios de sucesso (SC-001..SC-004) | 4 | 0 |
| Acceptance criteria (US1–US3, 7 ACs) | 7 | 0 |
| Decisões do plan (componentes/arquivos) | 6 | 0 |
| Princípios da Constituição (I–IV) | 4 | 0 |

**Todos os requisitos satisfeitos. Nenhuma tarefa de convergência necessária.**
