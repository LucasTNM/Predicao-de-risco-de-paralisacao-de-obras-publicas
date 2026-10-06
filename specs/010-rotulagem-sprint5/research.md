# Pesquisa e decisões — Sprint 5

Pesquisa local, incluindo agente somente leitura solicitado pelo fluxo speckit-plan; não depende de serviços externos.

## Fonte metodológica
PCC_Lucas_Tony.pdf: §2.4.2 (PDF 17, impressa 16) e §3.2 (PDF 28, impressa 27), texto extraído e páginas visualmente verificadas. O PCC define categorias, não um dicionário exaustivo dos valores da planilha. ADR-001 amplia exemplos e fixa corte até 2025. Logo, o catálogo desta sprint é operacionalização conservadora, não tabela literal publicada pelo TCU.

## Decisão: correspondência exata e conservadora
Normalizar apenas acentos/caixa/espaços da causa para lookup; preservar texto original. Classe 1: dificuldade técnica do tomador, deficiência de projeto, licenciamento ambiental e problemas técnicos da obra. Classe 2: atraso/falta de pagamento, contrapartida e categorias orçamentário-financeiras explícitas. Classe 3: abandono explícito e pedido de distrato pela contratada. Exigir situação paralisada para regras automáticas.
Racional: não resolver por palavra-chave a sobreposição entre problema técnico da empresa e falha da contratada. Alternativas rejeitadas: classificar todo termo técnico/financeiro; escolher classe de maior valor; tratar rescisão genérica como abandono. Dificuldade financeira/técnica da executora, orçamento genérico, rescisão, judicial, falha de execução e causas múltiplas ficam para revisão.

## Decisão: classe 0 apenas por evidência positiva revisada
23.526 causas vazias em 2025 não significam regularidade; há 60 concluídas com pendência, 87 reiniciadas e 15 concluídas com causa preenchida. Não usar situação nominal como prova de ausência de apontamentos. Primeira carga pode ter zero classe 0; reportar lacuna de contraste.
Alternativa rejeitada: causa vazia + concluída/em execução => zero.

## Decisão: proveniência no contrato existente
JSON em origem_rotulo com método, versão/hash, fingerprint, regra/evidência e data de execução. Estado ROTULADO significa preenchido tecnicamente, não homologação humana. Mantém cinco tabelas e assinatura DDL; relatórios locais preservam baseline e decisões. Alternativa: nova tabela de eventos, adiada até necessidade de histórico multiusuário.

## Decisão: invalidação e concorrência
Fonte inteira e medidas participam do fingerprint. Reload invalida ao mudar fonte, mesmo sem mudar causa. Aplicação bloqueia escrita concorrente nas tabelas fonte durante leitura/validação/update em transação; outro lote falha sem escrita. Rótulo divergente nunca sobrescrito silenciosamente. Auditor verifica evidência local revisada sempre que executado.

## Decisão: revisão com fonte textual original
JSON de decisões contém arquivo UTF-8 de evidência original/transcrição fiel, SHA-256, data, trecho, revisor e justificativa. A autenticidade e interpretação são responsabilidade do revisor declarado; o programa verifica estrutura, hash, trecho e corte temporal. Não alegar autenticação de identidade ou verificação jurídica da fonte. Fichas sintéticas e fontes não confirmadas são recusadas.

## Decisão: sem treino nesta sprint
Rotulagem retrospectiva não comprova previsão. Pesos de classe e splits requerem rótulos homologados e isolamento por obra. Nada a resolver mediante nova biblioteca ou pesquisa web nesta entrega.

SHA-256 PCC local: `e0ae5f011a51639669a6bc4290c7b94224b3a4e361c5af7db7b2f149a34ef329`.
