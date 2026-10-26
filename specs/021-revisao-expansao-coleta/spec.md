# Feature Specification: 021-revisao-expansao-coleta

**Feature Branch**: `021-revisao-expansao-coleta`  
**Created**: 2026-10-19  
**Status**: Active (Pausa Estratégica de Reengenharia de Coleta antes da Sprint 8)  
**Input**: Pausa estratégica entre a Sprint 7 e a Sprint 8 para auditar o descarte documental da Sprint 1, expandir o motor de ingestão para formatos ricos (`.pdf`, `.docx`, `.odt`, `.rtf`) e descompactação cirúrgica in-memory de `.zip` com gatekeeper anti-lixo rigoroso ($\ge 800$ caracteres úteis), e sondar novos endpoints públicos (Transferegov Web/API, PNCP Contratos/Aditivos/Rescisões, SIMEC Obras 2.0, SISMOB e DNIT) sobre uma amostra de 50 obras paralisadas de 2025.

## Contexto e Motivação

Ao concluir a Sprint 7 (Features 018, 019 e 020), constatamos que a remoção obrigatória das fichas sintéticas (por vazamento de alvo) reduziu a cobertura de documentos autênticos em obras paralisadas da base 2025 para apenas **12 obras** (11 na Classe 1, 1 na Classe 2 e 0 na Classe 3). Antes de iniciar o treinamento supervisionado final do BERTimbau + LoRA (Sprint 8 / Feature 022), esta Feature 021 executa uma investigação e reengenharia de coleta 100% isolada para verificar:
1. Quantos documentos densos foram bloqueados pelas regras estritas da Sprint 1 (extensões não-PDF, pacotes `.zip` e blacklist de termos como `"despacho"`, `"publicação"`, `"notificação"`, etc.);
2. Qual o ganho empírico real de cobertura e densidade textual ao expandir para múltiplos formatos (`.docx`, `.odt`, `.rtf`, `.zip` in-memory) e novos endpoints de execução contratual/vistorias em uma amostra controlada de **50 obras paralisadas de 2025**.

## Regras de Isolamento e Segurança (Guardrails Invioláveis)

1. **Isolamento Total de Diretório**: Todos os scripts exploratórios, extratores multiformato, logs de sondagem, amostras e artefatos de teste DEVEM residir estritamente dentro de `revisao_coleta/` e `specs/021-revisao-expansao-coleta/`.
2. **Preservação do Estado Atual (Read-Only no Core)**: É estritamente proibido alterar o schema `tcc` no PostgreSQL, modificar código em `src/` ou tocar nos lotes congelados da Sprint 7 (`dados_processados/sprint7/`) até que o relatório final (`report.md`) seja homologado pelo pesquisador.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auditoria Quantitativa do Código e Logs da Sprint 1 (Priority: P1)

Como Tech Lead e pesquisador, quero auditar estaticamente e dinamicamente os extratores atuais (`src/extractors/pncp.py`, `src/extractors/transferegov.py`, `src/extractors/tecnicos.py`, `src/utils.py`) e os logs históricos de coleta (`logs/sistema.log*` e `log_coleta.csv`) para quantificar exatamente quantos arquivos foram bloqueados por extensão (`.docx`, `.doc`, `.odt`, `.rtf`, `.zip`) e quantos documentos vitais (*Termos Aditivos*, *Memoriais Descritivos*, *Projetos Básicos*, *Pareceres Técnicos*, *Termos de Rescisão/Paralisação*, *Relatórios de Vistoria*) foram descartados pela heurística `filtro_pre_download_dom` ou por limitações de rota.

**Why this priority**: Diagnostica com precisão matemática onde ocorreram as perdas de recall documental na Sprint 1 e orienta a reengenharia das fases seguintes.

**Independent Test**: Script `revisao_coleta/fase1_auditoria_codigo_logs.py` executa a análise dos logs e do código-fonte e gera um JSON/Markdown auditável com contagens exatas de bloqueios por barreira, por extensão e por termo da blacklist.

**Acceptance Scenarios**:

1. **Given** os códigos em `src/extractors/` e `src/utils.py` e os logs em `logs/sistema.log*`, **When** o script de auditoria da Fase 1 for executado, **Then** são reportados os números exatos de descartes na Barreira 1 (DOM/API), Barreira 2 (SHA-256), Barreira 3 (Poda NLP) e descartes por extensão/formato.
2. **Given** a função `filtro_pre_download_dom`, **When** avaliada contra títulos reais de documentos de engenharia e rescisão, **Then** identifica-se a colisão de precedência onde `_BLACKLIST_TERMOS` (ex.: `"despacho"`, `"publicação"`, `"notificação"`) bloqueia documentos mesmo quando contêm termos da `_WHITELIST_TERMOS` (ex.: *"Despacho de Paralisação / Parecer Técnico"*, *"Publicação de Termo Aditivo"*, *"Notificação de Rescisão Contratual"*).

---

### User Story 2 - Motor de Ingestão Multiformato, Descompactação Cirúrgica In-Memory e Gatekeeper Anti-Lixo (Priority: P1)

Como Engenheiro de Dados Sênior, quero projetar e testar em `revisao_coleta/` um novo motor de ingestão capaz de extrair texto rico de `.pdf`, `.docx`, `.odt` e `.rtf`, inspecionar arquivos `.zip` em memória (`ZipFile.infolist()`) extraindo apenas documentos de texto rico e ignorando arquivos pesados de engenharia/mídia (`.dwg`, `.jpg`, `.mp4`, `.xlsx`), e aplicar um Gatekeeper Anti-Lixo rigoroso ($\ge 800$ caracteres úteis e rejeição de e-mails/capas/DOU curtos).

**Why this priority**: Muitos órgãos públicos anexam pastas técnicas compactadas (`.zip`) ou pareceres/memoriais em `.docx`/`.odt`/`.rtf`, que eram 100% ignorados ou salvos com extensão `.pdf` forçada na Sprint 1.

**Independent Test**: Suíte de testes e validação em `revisao_coleta/test_motor_multiformato.py` que submete arquivos reais e sintéticos (`.pdf`, `.docx`, `.odt`, `.rtf` e `.zip` misto contendo `.dwg`/`.jpg`/`.docx`/`.pdf`) e comprova extração limpa e bloqueio implacável de e-mails/despachos curtos ($< 800$ chars úteis).

**Acceptance Scenarios**:

1. **Given** um arquivo `.zip` contendo `.dwg`, `.jpg`, `.xlsx`, `.pdf` e `.docx`, **When** processado pelo inspetor in-memory, **Then** apenas `.pdf`, `.docx` e `.odt` (e `.rtf`) são extraídos em memória sem gravar lixo de imagem/CAD em disco.
2. **Given** um documento extraído, **When** submetido ao Gatekeeper Anti-Lixo, **Then** ele só é aprovado se possuir estrutura válida, densidade semântica $\ge 800$ caracteres úteis de texto corrido (excluindo cabeçalhos repetitivos e metadados tabulares) e não der match na regex de comprovante de e-mail (`De:`, `Para:`, `Assunto:`, `Enviado em:`).

---

### User Story 3 - Sondagem Profunda de Novos Endpoints em 50 Obras Paralisadas de 2025 (Priority: P1)

Como Especialista em MLOps, quero executar um benchmark real de requisições HTTP/API/DOM sobre uma amostra estratificada de **50 obras paralisadas de 2025** (priorizando CAIXA/Transferegov, SIMEC, SISMOB e DNIT que ficaram sem documento autêntico na Sprint 7) investigando novos endpoints:
1. **Transferegov (Web + API de Dados Abertos + Obrasgov CIPI)**: abas/endpoints de Execução, Acompanhamento/Vistoria, Termos Aditivos, Plano de Trabalho, Restrições/Paralisação e API de Dados Abertos (`api.transferegov.gestao.gov.br` / `api-publica.obrasgov.gestao.gov.br`).
2. **PNCP (Contratos, Termos Aditivos e Rescisões)**: consultar `/orgaos/{cnpj}/contratos` e termos de contrato/aditivos/rescisões além de `/compras`.
3. **SIMEC (Obras 2.0) e SISMOB**: sondar `simec.mec.gov.br/obras2` / `painelObras` (abas de Restrições e Inconformidades, Vistorias/Supervisão, Documentos Anexos) e a API pública do SISMOB Cidadão (`sismobcidadao.saude.gov.br/api/public/obras`).

**Why this priority**: É nos termos aditivos, termos de rescisão, históricos de paralisação e relatórios de vistoria/restrições que a causa real da paralisação se encontra documentada.

**Independent Test**: Execução do runner `revisao_coleta/fase3_sondagem_50_obras.py` sobre as 50 obras paralisadas amostrais, salvando os logs detalhados em `revisao_coleta/` e consolidando o relatório comparativo em `specs/021-revisao-expansao-coleta/report.md`.

**Acceptance Scenarios**:

1. **Given** a amostra de 50 obras paralisadas de 2025 sem documento autêntico prévio (ou com baixa cobertura), **When** sondada nos novos endpoints e formatos, **Then** cada tentativa HTTP/API é registrada com status, formato encontrado, quantidade de documentos/textos aprovados pelo Gatekeeper ($\ge 800$ chars) e densidade média.
2. **Given** os resultados do benchmark das 50 obras, **When** `specs/021-revisao-expansao-coleta/report.md` for gerado, **Then** ele apresenta a tabela comparativa obrigatória (*Fonte | O que pegávamos antes | O que descobrimos nos novos endpoints/formatos | Ganho de cobertura (%) em obras paralisadas | Densidade média (chars) dos novos documentos*).

---

## Edge Cases

- **Arquivos `.zip` com dezenas de fotos/plantas pesadas**: O coletor inspeciona `ZipFile.infolist()` antes de descompactar qualquer membro, ignorando entradas com extensões de mídia/CAD (`.jpg`, `.png`, `.mp4`, `.dwg`, `.dxf`, `.xlsx`, `.csv`, `.rar`) ou que excedam limite de segurança em memória.
- **Arquivos renomeados incorretamente como `.pdf` na Sprint 1**: Na Sprint 1, `pncp.py` salvava qualquer download com sufixo `.pdf` (`nome_arquivo = f"..._{sufixo}.pdf"`), fazendo com que arquivos `.zip`, `.docx` ou `.rar` baixados do PNCP falhassem na checagem de magic bytes `b"%PDF-"` do `inspect_pdf.py` e fossem descartados na Barreira 3 como `SEM_OCR`. O novo motor detecta o formato real pelos *magic bytes* (`PK\x03\x04` para ZIP/DOCX/ODT, `%PDF-` para PDF, `{\rtf` para RTF) além da extensão!
- **Portais com bloqueio reCAPTCHA ou SAML (ex.: SIMEC Obras 2.0 / Transferegov Web)**: O sondador utiliza sessões HTTP com cookies quando aplicável, respeita limites de timeout, e combina a sondagem DOM com as APIs públicas oficiais de Dados Abertos (`api.transferegov.gestao.gov.br`, `api-publica.obrasgov.gestao.gov.br`, `sismobcidadao.saude.gov.br`), registrando de forma transparente onde há acesso público direto vs. bloqueio por autenticação/captcha.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Todo o código, amostras, caches e logs desta feature DEVEM ficar isolados em `revisao_coleta/` e `specs/021-revisao-expansao-coleta/`, sem qualquer escrita no schema `tcc` do PostgreSQL ou modificação nos lotes congelados da Sprint 7.
- **FR-002**: A auditoria da Fase 1 DEVE inspecionar `src/extractors/pncp.py`, `src/extractors/transferegov.py`, `src/extractors/tecnicos.py`, `src/utils.py` e os arquivos de log (`logs/sistema.log*` e `log_coleta.csv`), reportando números exatos de arquivos bloqueados por extensão/formato e por filtro de metadados/DOM.
- **FR-003**: O motor de ingestão da Fase 2 (`revisao_coleta/motor_multiformato.py`) DEVE suportar extração textual nativa de `.pdf`, `.docx` (via `python-docx`), `.odt` e `.rtf`, detectando formatos tanto pelo nome quanto por *magic bytes* / estrutura interna.
- **FR-004**: O inspetor de `.zip` in-memory DEVE ler `ZipFile.infolist()`, filtrar e ignorar arquivos de engenharia/imagem/planilha (`.dwg`, `.jpg`, `.jpeg`, `.png`, `.mp4`, `.xlsx`, `.xls`, `.csv`) e extrair em memória apenas `.pdf`, `.docx`, `.odt` e `.rtf` (inclusive em subpastas ou `.zip` aninhado de 1º nível).
- **FR-005**: O Gatekeeper Anti-Lixo DEVE exigir estrutura válida, densidade semântica mínima de $\ge 800$ caracteres úteis de texto corrido (após remoção de cabeçalhos repetitivos e metadados tabulares) e rejeitar automaticamente por regex comprovantes de envio de e-mail (`De:`, `Para:`, `Assunto:`, `Enviado em:`), capas de processo vazias, despachos de 1 parágrafo e espelhos HTML vazios.
- **FR-006**: O filtro pré-download revisado (`filtro_pre_download_dom_v2`) DEVE priorizar termos vitais de engenharia e execução contratual (*Termos Aditivos*, *Memoriais Descritivos*, *Projetos Básicos*, *Pareceres Técnicos*, *Termos de Rescisão/Paralisação*, *Relatórios de Vistoria*, *Laudos*), impedindo que palavras genéricas como `"despacho"`, `"publicação"` ou `"notificação"` descartem esses documentos antes da inspeção de conteúdo.
- **FR-007**: A sondagem da Fase 3 DEVE selecionar uma amostra real e reprodutível (semente 42) de **50 obras paralisadas de 2025** (priorizando CAIXA/Transferegov, SIMEC, SISMOB e DNIT sem documento autêntico) e executar requisições reais aos novos endpoints (Transferegov Web/API/CIPI, PNCP Contratos/Aditivos/Rescisões, SIMEC Obras 2.0 / Painel Obras e SISMOB API).
- **FR-008**: O relatório final `specs/021-revisao-expansao-coleta/report.md` DEVE consolidar as descobertas das Fases 1, 2 e 3 e apresentar a tabela comparativa obrigatória com ganho de cobertura (%) e densidade média (chars) por fonte.
- **FR-009 (Pós-Aprovação — Etapa 1)**: Após aprovação do usuário, promover o motor multiformato (`src/extractors/multiformato.py`), o Gatekeeper Anti-Lixo ($\ge 800$ chars úteis + bloqueio regex de e-mails/DOU/capas) e os novos endpoints profundos para os módulos de produção (`src/config.py`, `src/utils.py`, `src/extractors/transferegov.py`, `src/extractors/pncp.py`, `src/extractors/tecnicos.py`, `src/main.py`), eliminando a geração de fichas sintéticas FPDF em produção.
- **FR-010 (Pós-Aprovação — Etapa 2)**: Habilitar suporte multi-ano completo (`2022`, `2023`, `2024`, `2025`, `2026`) em `src/config.py`, `src/main.py`, `src/database/run_load.py` e extratores, incluindo cache de reuso entre anos para obras idênticas (`(base, id_obra)`) que aparecem em múltiplos painéis anuais do TCU e ignorando fichas sintéticas legadas na checagem de obras concluídas.

### Key Entities

- **Relatório de Auditoria Sprint 1 (`auditoria_sprint1.json`)**: Contabilização exata de descartes por barreira (`FILTRO API`, `FILTRO DOM`, `DEDUP SHA-256`, `PODA NLP`), falsos negativos da blacklist e arquivos não-PDF corrompidos por renomeação forçada para `.pdf`.
- **Motor Multiformato & Gatekeeper (`motor_multiformato.py`)**: Componente isolado de parsing in-memory para `.pdf`, `.docx`, `.odt`, `.rtf` e `.zip` com validador de densidade semântica ($\ge 800$ chars úteis) e filtro regex anti-email/anti-lixo.
- **Amostra de Sondagem (`amostra_50_obras_paralisadas_2025.json`)**: Conjunto de 50 obras paralisadas de 2025 selecionadas para o benchmark empírico de novos endpoints.
- **Resultado de Benchmark (`benchmark_50_obras_resultados.json`)**: Registro detalhado por obra e por endpoint sondado, com documentos recuperados, formatos, caracteres úteis e diagnóstico técnico.

---

## Success Criteria *(mandatory)*

- **SC-001**: 100% de isolamento preservado — zero alterações no schema `tcc` do PostgreSQL e zero modificações nos arquivos congelados de `dados_processados/sprint7/` e `src/`.
- **SC-002**: Diagnóstico da Fase 1 respondido com números exatos extraídos dos logs e do código-fonte da Sprint 1.
- **SC-003**: Motor multiformato da Fase 2 validado com 100% de aprovação nos testes de `.pdf`, `.docx`, `.odt`, `.rtf`, inspeção seletiva de `.zip` in-memory e bloqueio de lixo/e-mails ($< 800$ chars úteis).
- **SC-004**: Sondagem real da Fase 3 executada sobre as 50 obras paralisadas de 2025 cobrindo Transferegov (Web + API), PNCP (Contratos/Aditivos/Rescisões), SIMEC (Obras 2.0) e SISMOB/DNIT, com resultados documentados na tabela comparativa de `specs/021-revisao-expansao-coleta/report.md`.
