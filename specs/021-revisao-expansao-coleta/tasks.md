# Tasks: Revisão e Expansão de Coleta Documental (Feature 021)

**Feature**: `021-revisao-expansao-coleta`  
**Input**: Design documents from `specs/021-revisao-expansao-coleta/` (`spec.md`, `plan.md`)  
**Prerequisites**: Isolamento estrito em `revisao_coleta/` e `specs/021-revisao-expansao-coleta/`; preservação total do PostgreSQL (`schema tcc`) e dos lotes congelados da Sprint 7.

---

## Phase 1: Setup & Isolamento (Foundational)

**Purpose**: Garantir estrutura isolada em `revisao_coleta/` e verificar dependências de parsing multiformato sem tocar no código de produção (`src/`).

- [x] T001 Criar estrutura de diretórios isolada `revisao_coleta/` e `revisao_coleta/resultados/` e inicializar `revisao_coleta/__init__.py`
- [x] T002 Verificar disponibilidade das bibliotecas de parsing multiformato (`pymupdf`, `pypdf`, `python-docx`, `odfpy`, `striprtf`, `beautifulsoup4`, `requests`) no ambiente `.venv`

---

## Phase 2: User Story 1 - Auditoria do que Deixamos para Trás na Sprint 1 (Priority: P1) 🎯

**Goal**: Auditar `src/extractors/pncp.py`, `src/extractors/transferegov.py`, `src/extractors/tecnicos.py`, `src/utils.py`, `logs/sistema.log*` e `log_coleta.csv` para responder com números exatos quantos arquivos foram bloqueados por extensão (`.docx`, `.doc`, `.odt`, `.rtf`, `.zip`) e quantos documentos vitais foram descartados pelo `filtro_pre_download_dom` ou por falhas de rota.

**Independent Test**: Executar `revisao_coleta/fase1_auditoria_codigo_logs.py` e validar a geração de `revisao_coleta/resultados/fase1_auditoria_sprint1.json` com todas as contagens exatas.

- [x] T003 [US1] Implementar `revisao_coleta/fase1_auditoria_codigo_logs.py` para minerar `logs/sistema.log`, `logs/sistema.log.1`, `logs/sistema.log.2`, `log_coleta.csv` e inspecionar os mecanismos de descarte em `src/extractors/pncp.py`, `src/extractors/transferegov.py`, `src/extractors/tecnicos.py` e `src/utils.py`
- [x] T004 [US1] Executar `revisao_coleta/fase1_auditoria_codigo_logs.py` e consolidar diagnóstico numérico exato em `revisao_coleta/resultados/fase1_auditoria_sprint1.json`

---

## Phase 3: User Story 2 - Expansão Multiformato, Descompactação In-Memory e Gatekeeper Anti-Lixo (Priority: P1)

**Goal**: Projetar e testar em `revisao_coleta/motor_multiformato.py` a ingestão de `.pdf`, `.docx`, `.odt`, `.rtf`, a inspeção cirúrgica in-memory de `.zip` (`ZipFile.infolist()`) ignorando `.dwg`, `.jpg`, `.mp4`, `.xlsx`, e o Gatekeeper Anti-Lixo ($\ge 800$ caracteres úteis de texto corrido + bloqueio regex de e-mails `De:`/`Para:`/`Assunto:`/`Enviado em:`, capas de processo, DOU curto e espelhos HTML vazios), além do filtro DOM v2 que preserva *Termos Aditivos*, *Memoriais Descritivos*, *Projetos Básicos*, *Pareceres Técnicos*, *Termos de Rescisão/Paralisação* e *Relatórios de Vistoria*.

**Independent Test**: Executar `revisao_coleta/test_motor_multiformato.py` e verificar 100% de aprovação nos testes unitários e de integração multiformato.

- [x] T005 [US2] Implementar `revisao_coleta/motor_multiformato.py` contendo extratores in-memory para `.pdf`, `.docx`, `.odt`, `.rtf`, inspetor cirúrgico de `.zip` (`ZipFile.infolist()`), `filtro_pre_download_dom_v2` e `GatekeeperAntiLixo` ($\ge 800$ chars úteis + regex anti-email/anti-capa)
- [x] T006 [US2] Implementar e executar `revisao_coleta/test_motor_multiformato.py` validando todos os formatos (`.pdf`, `.docx`, `.odt`, `.rtf`, `.zip` misto com `.dwg`/`.jpg`/`.xlsx`) e regras do Gatekeeper, gerando `revisao_coleta/resultados/fase2_validacao_multiformato.json`

---

## Phase 4: User Story 3 - Sondagem Profunda de Novos Endpoints em 50 Obras Paralisadas de 2025 (Priority: P1)

**Goal**: Selecionar 50 obras paralisadas de 2025 (priorizando CAIXA/Transferegov, SIMEC, SISMOB e DNIT sem documento autêntico) e executar sondagem real HTTP/API/DOM nos novos endpoints:
1. Transferegov Web (abas Execução, Acompanhamento/Laudos de Vistoria, Termos Aditivos, Plano de Trabalho, Restrições/Paralisação) + API de Dados Abertos (`api.transferegov.gestao.gov.br`, `api-publica.obrasgov.gestao.gov.br`, dumps SICONV/CIPI);
2. PNCP Contratos (`/orgaos/{cnpj}/contratos`), Termos de Contrato, Termos Aditivos e Termos de Rescisão;
3. SIMEC Obras 2.0 (`simec.mec.gov.br/obras2` / `painelObras`) e SISMOB Cidadão (`sismobcidadao.saude.gov.br/api/public/obras`).

**Independent Test**: Executar `revisao_coleta/selecionar_amostra_50_obras.py` e `revisao_coleta/fase3_sondagem_50_obras.py`, gerando `revisao_coleta/resultados/amostra_50_obras_paralisadas_2025.json` e `revisao_coleta/resultados/fase3_benchmark_50_obras.json`.

- [x] T007 [US3] Implementar e executar `revisao_coleta/selecionar_amostra_50_obras.py` para extrair de forma determinística (semente 42) a amostra de 50 obras paralisadas de 2025 sem documento autêntico (cobrindo CAIXA/FUNASA/Transferegov, SIMEC, SISMOB e DNIT/CODEVASF)
- [x] T008 [US3] Implementar `revisao_coleta/sondagem_endpoints.py` com os conectores exploratórios profundos para Transferegov (Web abas internas + API Dados Abertos + Obrasgov CIPI), PNCP (Contratos + Termos Aditivos/Rescisão + Arquivos), SIMEC Obras 2.0 e SISMOB API
- [x] T009 [US3] Implementar e executar `revisao_coleta/fase3_sondagem_50_obras.py` aplicando os novos conectores e o `motor_multiformato.py` sobre as 50 obras paralisadas de 2025 e salvando telemetria completa em `revisao_coleta/resultados/fase3_benchmark_50_obras.json`

---

## Phase 5: Entregáveis Finais & Relatório Comparativo (`report.md`)

**Goal**: Consolidar todas as evidências empíricas das Fases 1, 2 e 3 em `specs/021-revisao-expansao-coleta/report.md` com a tabela comparativa exigida e verificar que zero arquivos fora de `revisao_coleta/` e `specs/021-revisao-expansao-coleta/` foram alterados.

- [x] T010 Gerar `specs/021-revisao-expansao-coleta/report.md` com respostas numéricas da Fase 1, validação do motor multiformato da Fase 2 e tabela comparativa da Fase 3 (*Fonte | O que pegávamos antes | O que descobrimos nos novos endpoints/formatos | Ganho de cobertura (%) em obras paralisadas | Densidade média (chars) dos novos documentos*)
- [x] T011 Auditar isolamento final (`git status`) e atualizar status de conclusão em `specs/021-revisao-expansao-coleta/tasks.md`

---

## Phase 6: Etapas 1 e 2 Pós-Aprovação — Refatoração de Produção (`src/`) & Suporte Multi-Ano (`2022`–`2026`)

**Goal**: Com o ganho empírico aprovado pelo usuário, refatorar os extratores e utilitários de produção (`src/config.py`, `src/utils.py`, `src/extractors/multiformato.py`, `src/extractors/transferegov.py`, `src/extractors/pncp.py`, `src/extractors/tecnicos.py`, `src/main.py`, `src/database/run_load.py`) para suportar todas as safras do painel do TCU (`2022`, `2023`, `2024`, `2025`, `2026`), ingestão multiformato (`.pdf`, `.docx`, `.odt`, `.rtf`), descompactação cirúrgica `.zip` in-memory, varredura de todas as abas internas do Transferegov/PNCP/SISMOB, eliminação de fichas sintéticas FPDF e reuso cross-ano O(1) de obras idênticas.

- [x] T012 Atualizar `src/config.py` e `src/database/run_load.py` para suportar `ANOS_PAINEL_TCU = ["2022", "2023", "2024", "2025", "2026"]` e helpers parametrizados por `ano_base`
- [x] T013 Criar `src/multiformato.py` (`src/extractors/multiformato.py`) e atualizar `src/utils.py` integrando detecção por magic bytes, extração `.pdf`/`.docx`/`.odt`/`.rtf`, descompactação `.zip` in-memory, `GatekeeperAntiLixo` ($\ge 800$ chars úteis), `filtro_pre_download_dom` com whitelist prioritária e materialização de documentos não-PDF em PDFs nativos UTF-8 compatíveis com `inspect_pdf.py` e `pdf_to_text.py`
- [x] T014 Refatorar `src/extractors/transferegov.py` com Selenium Manager resiliente (Edge 155+), varredura das 5 abas internas (`Pareceres`, `Termos Aditivos`, `Ajustes do PT`, `Licitações/Execução`, `Anexos Proposta/Convênio`), descompactação `.zip` in-memory e integração com API Obrasgov (`historico-situacao-cancelada-paralisada`)
- [x] T015 Refatorar `src/extractors/pncp.py` com `PNCPContractsIndex` (índice de contratos `/api/consulta/v1/contratos`), coleta de arquivos do contrato, `Termos Aditivos / Rescisões` (`/termos`) e arquivos `.zip`/multiformato da compra vinculada (`numeroControlePncpCompra`), mantendo 100% de compatibilidade com `tests/test_pncp_identity.py`
- [x] T016 Refatorar `src/extractors/tecnicos.py` para consultar a API pública oficial do SISMOB (`sismobcidadao.saude.gov.br/api/public/obras`) e desativar a geração de fichas sintéticas FPDF em produção
- [x] T017 Refatorar `src/main.py` para suportar execução multi-ano (`2022`–`2026` ou `--ano todos`), filtro `--apenas-paralisadas`, ignorar fichas sintéticas legadas no cache de obras concluídas e reutilizar documentos autênticos entre anos (`cross-year cache`) para obras com mesmo `(base, id_obra)`
- [x] T018 Executar bateria de testes automatizados (`tests/test_curadoria_nlp.py`, `tests/test_pncp_identity.py`, `tests/test_multiformato_producao.py`) e validação `--dry-run` sobre as planilhas `2022`–`2026`

---

## Phase 7: Execução em Larga Escala Multiano (`2022`–`2026`) & Supervisão `/goal`

**Goal**: Executar o download de ponta a ponta para todos os anos do TCU (`2022` a `2026`) com o orquestrador em produção, priorizando obras paralisadas e auditando o acervo final gravado no Google Drive.

- [x] T019 Executar download massivo multiano de obras paralisadas via `.\.venv\Scripts\python.exe src/main.py --modo coleta --ano todos --apenas-paralisadas` com monitoramento e sessão resiliente
- [x] T020 Auditar acervo consolidado no Google Drive (`G:\Meu Drive\TCC_DOCUMENTOS`) e atualizar `specs/021-revisao-expansao-coleta/report.md` comprovando o salto de 12 obras (baseline 2025) para 11.416 obras únicas com 126.738 documentos autênticos validados pelo Gatekeeper

---

## Phase 8: Passos 1 a 6 Pós-Coleta — Complementação 2022/PNCP, Parsing, Higienização, Carga PostgreSQL, RAG & Treino Sprint 8

**Goal**: Executar sequencialmente os Passos 1 a 6 em background (verificando apenas ao término de cada script para economia máxima de tokens):
1. Coleta complementar de `2022` e repasse `dnit,codevasf` com retry HTTP 429;
2. Parsing/OCR multiano (`--modo parsing --ano todos`);
3. Higienização NLP multiano (`--modo higienizacao --ano todos --skip-llm`);
4. Carga e validação no PostgreSQL (`--modo carga --ano todos --excluir-quarentena` + `--modo validar-banco`);
5. Atualização de rebaseline, auditoria de vazamento e extração de evidências RAG;
6. Treinamento final BERTimbau + LoRA, avaliação no teste retido e XAI (Feature 022 / Sprint 8).

- [x] T021 [Passo 1] Executar coleta complementar `2022` e repasse `dnit,codevasf` (`2022`–`2026`) — **Concluído: 2022 subiu de 34 para 4.097 obras (37.865 docs); total global 2022–2026: 164.571 documentos autênticos em 15.179 obras únicas**
- [x] T022 [Passo 2] Executar `--modo parsing --ano todos` para extrair textos dos PDFs validados — **Concluído: 163.386 documentos autênticos extraídos e auditados com SHA-256 nos 5 anos (2022–2026)**
- [x] T023 [Passo 3] Executar `--modo higienizacao --ano todos --skip-llm` para gerar textos limpos — **Concluído: 163.386 textos autênticos higienizados com 0 falhas nos 5 anos (2022–2026)**
- [x] T024 [Passo 4] Preparar Docker/PostgreSQL e executar `--modo carga --ano todos --excluir-quarentena` e `--modo validar-banco` — **Concluído: 132.568 obras/fatos (2022–2026), 191.274 documentos, 305.394 chunks únicos (`dim_embedding`), 618.732 vínculos (`ponte_documento_embedding`), `valido: true` (0 inconsistências)**
- [x] T025 [Passo 5] Atualizar rebaseline/auditoria anti-vazamento e regenerar evidências RAG sobre o novo corpus — **Concluído: 46.299 novos chunks vetorizados com GTE na RTX 5060; cobertura RAG saltou para 3.827 obras rotuladas (3.088 em `treino_dev` e 739 em `teste_retido`, 85,9% da Classe 1); no teste retido (3.632 obras), `C2_Oficial` (`Hierarquico_Campeao`) saltou de Macro-F1 `0.4462` (`C1`) para `0.5377` (+9,15 pp) e MCC de `0.3965` para `0.5508` (+15,43 pp)**
- [x] T026 [Passo 6] Executar treinamento BERTimbau + LoRA, avaliação no teste retido e XAI (Sprint 8 / Feature 022) — **Concluído: 5 dobras CV + modelos finais na RTX 5060; avaliação do teste retido (3.632 obras): `Hierarquico_C2_Texto_Autentico` campeão definitivo (Macro-F1 0.5377, MCC 0.5508); Sistema Híbrido sem ganho estatisticamente significante (Macro-F1 0.5366, p = 0.516); XAI com fidelidade de 60,94% e 0 vazamentos; relatório consolidado em `specs/022-treino-avaliacao-xai/report.md`**

---

## Dependencies & Execution Order

- **Phase 1 (T001–T002)** → bloqueia as demais fases.
- **Phase 2 (T003–T004)** e **Phase 3 (T005–T006)** → podem avançar sequencialmente; Phase 3 fornece o `motor_multiformato.py` usado na Phase 4.
- **Phase 4 (T007–T009)** → depende de `motor_multiformato.py` (T005) para validar e medir a densidade dos novos documentos/textos encontrados nos endpoints.
- **Phase 5 (T010–T011)** → consolida os resultados de T004, T006 e T009 no relatório final `report.md`.
