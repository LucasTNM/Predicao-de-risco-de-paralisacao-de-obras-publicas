# Implementation Plan: 021-revisao-expansao-coleta

**Branch**: `021-revisao-expansao-coleta` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/021-revisao-expansao-coleta/spec.md`

## Summary

Realizar uma Pausa Estratégica de Reengenharia de Coleta (100% isolada em `revisao_coleta/` e `specs/021-revisao-expansao-coleta/`) antes da Sprint 8 para:
1. **Fase 1 (Auditoria Sprint 1)**: Quantificar com números exatos a perda documental causada pelas regras restritivas da Sprint 1 nos extratores `src/extractors/pncp.py`, `src/extractors/transferegov.py`, `src/extractors/tecnicos.py` e `src/utils.py`, cruzando análise estática de código e mineração dos logs históricos (`logs/sistema.log*` e `log_coleta.csv`).
2. **Fase 2 (Motor Multiformato In-Memory + Gatekeeper Anti-Lixo)**: Construir em `revisao_coleta/motor_multiformato.py` um parser multiformato in-memory para `.pdf`, `.docx` (`python-docx`), `.odt` (`odfpy` / XML `content.xml`) e `.rtf` (`striprtf`), combinado com um descompactador cirúrgico de `.zip` (`ZipFile.infolist()`) que ignora arquivos pesados de engenharia/mídia (`.dwg`, `.jpg`, `.mp4`, `.xlsx`) e extrai apenas documentos de texto rico, além de um Gatekeeper Anti-Lixo rigoroso ($\ge 800$ caracteres úteis de texto corrido, exclusão de cabeçalhos repetitivos/metadados tabulares e bloqueio regex de comprovantes de e-mail `De:`/`Para:`/`Assunto:`/`Enviado em:`).
3. **Fase 3 e 4 (Sondagem Profunda em 50 Obras Paralisadas de 2025 e Relatório)**: Testar em uma amostra real e estratificada de **50 obras paralisadas de 2025** (priorizando CAIXA/Transferegov, SIMEC, SISMOB e DNIT sem documentos autênticos) os novos endpoints públicos (Transferegov Web abas de Execução/Acompanhamento/Aditivos/Plano de Trabalho/Restrições + API de Dados Abertos/Obrasgov CIPI; PNCP Contratos/Termos Aditivos/Rescisões; SIMEC Obras 2.0 / Painel Obras; SISMOB Cidadão API) e consolidar a tabela comparativa em `specs/021-revisao-expansao-coleta/report.md`.

## Technical Context

**Language/Version**: Python 3.14 (`.venv` local).

**Primary Dependencies**: `requests`, `beautifulsoup4`, `pymupdf` (`fitz`), `pypdf`, `python-docx`, `odfpy`, `striprtf`, `pandas`, `zipfile` (stdlib), `io.BytesIO` (stdlib).

**Storage & Isolation**:
- Diretório isolado de código, amostras, caches e logs: `revisao_coleta/`
- Diretório de especificação e relatório: `specs/021-revisao-expansao-coleta/`
- **PostgreSQL (`schema tcc`)**: Somente leitura (ou nem tocado; leitura de obras pode usar os parquets/planilhas e/ou consulta read-only). Zero `INSERT`/`UPDATE`/`DELETE`/`DDL`.
- **Lotes Sprint 7 (`dados_processados/sprint7/`)**: 100% intocados.

**Testing**: Script de validação unitária e de integração `revisao_coleta/test_motor_multiformato.py` cobrindo `.pdf`, `.docx`, `.odt`, `.rtf`, `.zip` cirúrgico in-memory e Gatekeeper Anti-Lixo ($\ge 800$ chars + regex e-mail).

**Target Platform**: Windows 11 local com conectividade HTTP/HTTPS para APIs e portais governamentais (`pncp.gov.br`, `discricionarias.transferegov.sistema.gov.br`, `api.transferegov.gestao.gov.br`, `api-publica.obrasgov.gestao.gov.br`, `simec.mec.gov.br`, `sismobcidadao.saude.gov.br`).

## Constitution Check

| Princípio | Exigência | Situação no desenho |
| :--- | :--- | :---: |
| I. Fidedignidade histórica e rótulo real | Evidências documentais devem ser autênticas; vedado uso de fichas sintéticas para suprir causa ausente | PASS: foco exclusivo em documentos autênticos de engenharia, termos aditivos, rescisões, vistorias e pareceres técnicos |
| II. Integridade semântica dos documentos | Limpeza e curadoria devem ter proveniência; barreira de densidade rigorosa contra ruído burocrático | PASS: Gatekeeper Anti-Lixo exige $\ge 800$ caracteres úteis de texto corrido e bloqueia e-mails/capas/despachos curtos |
| III. Consistência relacional e dimensional | Preservar schema `tcc` e lotes congelados da Sprint 7 sem mutação | PASS: isolamento total em `revisao_coleta/`; nenhuma escrita no banco ou em `dados_processados/sprint7/` |
| IV. Reprodutibilidade de ML e MLOps | Amostragem determinística (semente 42), HTTP direto com sessão reutilizável, logs auditáveis | PASS: amostra de 50 obras fixada com semente 42 e logs estruturados em JSON/Markdown |

## Project Structure

### Documentation (this feature)

```text
specs/021-revisao-expansao-coleta/
├── spec.md
├── plan.md
├── tasks.md
├── checklists/
│   └── requirements.md
└── report.md                  # Relatório executivo e científico com tabela comparativa das 4 fases
```

### Isolated Exploratory & Re-engineering Code (`revisao_coleta/`)

```text
revisao_coleta/
├── __init__.py
├── fase1_auditoria_codigo_logs.py      # Fase 1: Diagnóstico quantitativo dos logs e código da Sprint 1
├── motor_multiformato.py               # Fase 2: Extrator in-memory (.pdf, .docx, .odt, .rtf, .zip) + Gatekeeper (>= 800 chars)
├── test_motor_multiformato.py          # Fase 2: Testes automatizados do motor multiformato e Gatekeeper
├── selecionar_amostra_50_obras.py      # Fase 3: Seleção estratificada determinística das 50 obras paralisadas de 2025
├── sondagem_endpoints.py               # Fase 3: Clientes HTTP/API/DOM para Transferegov, PNCP Contratos, SIMEC Obras 2.0, SISMOB e Obrasgov
├── fase3_sondagem_50_obras.py          # Fase 3: Runner do benchmark real nas 50 obras paralisadas
└── resultados/                         # Artefatos JSON/CSV/amostras gerados pela auditoria e sondagem
    ├── fase1_auditoria_sprint1.json
    ├── fase2_validacao_multiformato.json
    ├── amostra_50_obras_paralisadas_2025.json
    └── fase3_benchmark_50_obras.json
```
