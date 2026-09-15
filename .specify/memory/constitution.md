# Constituição do TCC — Predição de Risco em Obras Públicas

## Core Principles

### I. Fidedignidade histórica e rótulo real (ADR-001, ADR-002, ADR-006)

O rótulo e as causas de risco DEVEM respeitar a taxonomia metodológica adotada no
diário a partir do Acórdão TCU 2600/2024 e a evidência física/factual documentada
até 2025. Estados administrativos de 2026 e informações posteriores NÃO DEVEM
substituir o alvo histórico ou contaminar atributos de treino. Snapshots de 2026
podem ser armazenados com proveniência; armazenamento não autoriza seu uso como
evidência histórica. Classes: 0 regular; 1 deficiência técnica; 2 deficiência
orçamentário-financeira; 3 abandono/falhas da contratada. Ausência de evidência
DEVE permanecer NULL/pendente, nunca virar classe 0 por padrão.

A amostragem futura DEVE conter contraste entre obras regulares e paralisadas,
registrar critérios e impedir que a mesma obra vaze entre treino e avaliação.
Fichas sintéticas derivadas de planilhas DEVEM ser distinguidas de documentos
originais para prevenir vazamento do alvo. Estes critérios preservam a validade
científica, sem inventar regra de rotulagem automática ainda não homologada.

### II. Integridade semântica dos documentos (ADR-004, ADR-007, ADR-008)

Limpeza e fragmentação DEVEM preservar números de contratos/processos, datas,
valores monetários, dispositivos legais, nomes, stopwords e símbolos como nº.
É proibido resumir ou remover informação de domínio para facilitar o processamento.
O texto canônico de cada chunk DEVE corresponder ao recorte pelos offsets do
documento; IDs WordPiece exatos DEVEM ser preservados, inclusive nas bordas.

As três barreiras de curadoria (metadados, SHA-256 e densidade) e os estados de
coleta, extração/OCR e higienização DEVEM ter proveniência. Uma etapa posterior
bem-sucedida não revoga rejeição anterior. Arquivos ausentes, alterados, ambíguos
ou de qualidade insuficiente DEVEM ser excluídos/quarentenados com motivo.
Fallback OCR e LLM DEVEM ser seletivos e verificáveis; LLM não pode inventar dados.

### III. Consistência relacional e dimensional (ADR-009)

A fato_risco DEVE manter uma observação por obra/data-base, inclusive obras sem
documentos. Medidas financeiras exatas NÃO DEVEM ser somadas após expansão N:N.
As cinco tabelas de negócio DEVEM preservar PKs, FKs, unicidade e checks; a ponte
liga fato, documento e fragmento e guarda ordem/offsets por ocorrência.

Sliding Window usa BERTimbau cased com revisão fixa, 450 tokens de conteúdo e 50
de sobreposição por padrão, reservando especiais dentro do limite 512. Não pode
haver lacunas, cauda perdida ou janela final redundante. Reuso de conteúdo exige
igualdade de texto, tokens e configuração. Embeddings vector(768) e metadados
de geração permanecem NULL na Sprint 3. Mudanças no esquema, texto ou contrato de
tokenização exigem migração/reprocessamento explícito e transacional.

### IV. Reprodutibilidade de ML e MLOps (ADR-003, ADR-005, ADR-007)

Versões, revisões, parâmetros, fontes e resultados DEVEM ser registrados.
Experimentos estocásticos DEVEM fixar e registrar sementes; nenhuma semente é
necessária para algoritmos determinísticos. Cache de idempotência DEVE usar
consultas O(1) após leitura única dos manifestos. Concorrência DEVE usar sessões
isoladas, escrita protegida e limites explícitos; preservar HTTP direto com
cookie-sharing onde já adotado, sem reintroduzir navegadores por documento.

Arquivos DEVEM ser persistidos atomicamente antes do registro de sucesso no
manifesto (protocolo Write-Ahead Logging adotado pelo projeto); cargas no banco
DEVEM confirmar documento, chunks e vínculos numa transação e relatar sucesso
somente após commit. Falhas e retomadas NÃO DEVEM produzir estado parcial.
Pytest e testes de integração afetados DEVEM passar antes de qualquer commit.
Credenciais, corpus, logs operacionais e bancos de teste NÃO DEVEM ser versionados.

## Rastreabilidade metodológica

Fonte: `docs/TCC_Dev_Diary.md`, ADRs aprovadas de 2026-08-17 a 2026-09-09.
O diário é local e ignorado pelo Git; esta constituição torna seus guardrails
versionáveis, sem afirmar que números históricos foram medidos novamente.

| ADR | Decisão preservada | Artigo |
| --- | --- | --- |
| 001 | Alvo histórico e quatro classes causais | I |
| 002 | Extração completa e contraste amostral | I |
| 003 | Cache O(1), sessões e escrita concorrente protegida | IV |
| 004 | Três barreiras de curadoria | II |
| 005 | HTTP direto, cookie-sharing e concorrência limitada | IV |
| 006 | Base histórica e distinção de fichas sintéticas | I |
| 007 | Extração/OCR seletivo, persistência atômica e retomada | II, IV |
| 008 | Preservação semântica e limpeza em duas camadas | II |
| 009 | Estrela, ponte N:N e WordPiece determinístico | III |

## Fluxo de desenvolvimento e critérios de revisão

Antes de implementar, aplicar Spec Kit: constituição → spec.md → plan.md →
tasks.md → implementação → converge. Especificações e evidências DEVEM ficar em
`specs/`; `.specify/` e `.agents/skills/` devem ser versionáveis, exceto estado local.
Auditorias DEVEM separar testes unitários, integração real, piloto e carga integral.
Uma carga piloto NÃO homologa o corpus completo. Pendências devem ser documentadas
com evidência; não executar embeddings, treinamento ou reclassificação na Sprint 3.

## Governance

Esta versão formaliza as nove ADRs existentes e o pedido de adoção do Spec Kit.
Toda revisão DEVE verificar os quatro artigos. Emendas exigem justificativa,
rastreabilidade à decisão metodológica e impacto em dados, testes e especificações.
Usar SemVer: major para mudar/remover princípios, minor para ampliar regras e patch
para esclarecimentos sem alteração semântica. Mudanças metodológicas não podem ser
introduzidas silenciosamente por correção técnica. Preservar trabalho local existente.

**Version**: 1.0.0 | **Ratified**: 2026-09-10 | **Last Amended**: 2026-09-10
