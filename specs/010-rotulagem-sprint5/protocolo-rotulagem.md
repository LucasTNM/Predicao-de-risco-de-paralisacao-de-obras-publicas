> Atualização posterior: a feature [011](../011-situacao-causa-risco/plan.md) autoriza classe 0 pela situação sem contradições e adiciona recuperação de causas ausentes. Este documento preserva a etapa v1.

# Protocolo operacional de rotulagem — Sprint 5

Fonte: PCC §2.4.2 e §3.2 (páginas impressas 16 e 27), ADR-001 e constituição. Estes números são categorias nominais, não escala ordinal de gravidade. O catálogo abaixo é uma decisão operacional conservadora do projeto; o PCC não lista cada motivo bruto da planilha.

| Classe | Significado | Evidência exigida |
| --- | --- | --- |
| 0 | Regular / sem risco evidenciado | Revisão explícita de evidência histórica original, com regularidade e ausência de apontamentos graves declaradas pelo revisor |
| 1 | Deficiência técnica | Causa técnica inequívoca no catálogo ou decisão revisada |
| 2 | Deficiência orçamentário-financeira | Causa financeira inequívoca no catálogo ou decisão revisada |
| 3 | Abandono da contratada | Abandono/desistência expressos no catálogo ou decisão revisada |
| NULL | Pendente | Evidência ausente, ambígua, conflitante ou fora do corte; não é quinta classe de treino |

## Catálogo automático
Todas as regras exigem observação de 2025 e situação normalizada `Paralisada`. Lookup da causa completa, com normalização de acentos, caixa e espaços; texto de origem permanece intacto.

| Regra | Classe | Causa original | Fundamento |
| --- | --- | --- | --- |
| T01 | 1 | Dificuldade técnica do Tomador | Incapacidade técnica institucional; PCC 2.4.2. |
| T02 | 1 | Deficiência do Projeto | Falha de projeto; PCC 2.4.2. |
| T03 | 1 | Licenciamento ambiental | Licença ambiental; ADR-001. |
| T04 | 1 | Problemas técnicos da obra | Causa técnica explícita; PCC 2.4.2. |
| F01 | 2 | Paralisação por falta de pagamento à empresa executora | Falta de pagamento; PCC 2.4.2/ADR-001. |
| F02 | 2 | Atraso no Pagamento Construtora | Atraso no pagamento; PCC 2.4.2/ADR-001. |
| F03 | 2 | Falta de aporte de contrapartida | Contrapartida; PCC 2.4.2. |
| F04 | 2 | ORCAMENTARIA/FINANCEIRA UNIAO | Fluxo financeiro da União; PCC 2.4.2. |
| F05 | 2 | Orçamentário/Financeiro | Causa orçamentário-financeira explícita; PCC 2.4.2. |
| A01 | 3 | Abandono da empresa | Abandono explícito; PCC 2.4.2. |
| A02 | 3 | Abandono pela empresa | Abandono explícito; PCC 2.4.2. |
| A03 | 3 | ABANDONO POR PARTE DA CONTRATADA | Abandono explícito; PCC 2.4.2. |
| A04 | 3 | PEDIDO DE DISTRATO AMIGAVÉL POR PARTE DA CONTRATADA (RECISÃO). | Desistência expressa da contratada; ADR-001. |

## Exceções deliberadas
- Rescisão genérica não comprova desistência/abandono da empresa.
- Dificuldade técnica da empresa, falha de execução e desconformidade podem se sobrepor a falhas da contratada; revisar agente e causa predominante.
- Dificuldade financeira da executora não demonstra falta de repasse nem abandono. Deficiência genérica de orçamento pode indicar erro de projeto/orçamento ou falta de recursos.
- Judicial, embargos, gestão, clima, infraestrutura, licenças não especificadas, terreno, auditoria e outros exigem contexto.
- Causas múltiplas não têm prioridade por número nem recorte por substring.
- Causa de risco em obra nominalmente concluída/em execução exige revisão de cronologia.
- Ausência de causa não demonstra regularidade. Nenhuma classe 0 automática.
- Observações de 2026 não recebem classe nesta política e não são transferidas entre anos.

## Revisão e alcance da validação
O comando de revisão confere arquivo UTF-8 original/transcrição fiel, SHA-256, trecho, data, snapshot, revisor declarado e justificativa. O arquivo e o trecho devem permitir examinar o caso concreto. A declaração humana de origem não é verificação independente de autenticidade; essa responsabilidade permanece com o pesquisador. Classe 0 exige `regularidade_sem_apontamentos_graves=true` e prova correspondente. Regras automáticas não recebem nome de revisor humano nem alegação de gold standard.

Uma decisão diferente da já persistida é rejeitada. Corrigir um rótulo revisado requer procedimento explícito futuro; a ferramenta não oferece sobrescrita silenciosa. Reload com fonte alterada revoga o rótulo atual para PENDENTE, mantendo a execução anterior nos relatórios locais. Mudança de arquivo de evidência reprova auditoria e bloqueia novos lotes até resolução.

## Contraste e próximo experimento
O primeiro lote de regras pode não conter classe 0. Antes de treinar, revisar casos regulares e classes raras, homologar regras e fontes, definir amostra e separar obras/textos compartilhados. Nem causa original, nem justificativa de rótulo, nem ficha sintética derivada do alvo podem ser tratadas como atributos preditivos sem auditoria de vazamento. A rotulagem atual é retrospectiva.

Versão: `pcc-adr001-conservadora-v1`. SHA-256 do módulo da política: `e0a30dcb2c27a176ce55b8c667db097af3ad8f5100ed4f0459d98a9037e4d8a2`.
