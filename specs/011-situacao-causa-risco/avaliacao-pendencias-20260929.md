# Avaliação das obras paralisadas restantes

**Data da avaliação:** 2026-09-29. **Escopo:** proposta metodológica e operacional, sem reclassificar dados ou iniciar coleta massiva.
**Base empírica:** snapshots auditados em 2026-09-28 (`sprint5_inventario_final`, `sprint5_v2_recuperacao`, `sprint5_v2_auditoria`), com confirmação no PostgreSQL em 2026-09-29 após ativação do Docker. A consulta em transação somente leitura confirmou os totais de paralisadas, rótulos, causas ausentes e distribuição documental por base; a auditoria dos rótulos passou e nenhum registro de 2026 está rotulado. Os detalhamentos de causas e situações originais derivam dos snapshots. Não houve nova auditoria integral dos arquivos do corpus. Registros: `logs/sprint5_avaliacao_pendencias_20260929.json` (avaliação inicial) e `logs/sprint5_avaliacao_confirmacao_banco_20260929.json` (confirmação ao vivo).

## Recomendação principal
Tratar a ausência de causa como problema de obtenção/verificação de evidência, não de imputação estatística. Preservar o fato conhecido — situação tabular Paralisada — sem fingir que sua causa 1/2/3 é conhecida. Priorizar duas frentes: revisão do catálogo para causas já descritas e piloto de recuperação histórica nas bases com causa ausente. Expandir coleta somente depois de medir rendimento e custo.

Não treinar um modelo com os próprios rótulos atuais para preencher todos os nulos e depois chamar essas previsões de verdade observada. Não converter nulos em 0, usar classe modal, inventar uma quinta classe causal ou copiar a causa de obra semelhante.

## 1. Dimensão real das pendências

| Grupo histórico 2025 | Obras | Tratamento |
| --- | ---: | --- |
| Paralisadas já rotuladas | 1.505 | Preservar proveniência; validar amostra cientificamente |
| Paralisadas com causa presente, mas ambígua/não mapeada | 3.181 | Revisar taxonomia/contexto antes de coletar tudo de novo |
| Paralisadas sem causa utilizável | 6.783 | Recuperação por identidade da obra e data-base |
| Total de paralisadas | 11.469 | 9.964 ainda pendentes |

Os 170 conflitos em Em execução/Concluída são uma fila separada e não integram as 9.964 paralisadas pendentes. 6.783 = 6.738 SQL NULL + 45 hífen/Não informado. Rótulos existentes e corte histórico permanecem inalterados.

### Distribuição da causa ausente por base

| Base | Sem causa | Situação documental |
| --- | ---: | --- |
| SISMOB | 3.941 | Fichas sintéticas |
| SIMEC | 1.986 | Fichas sintéticas |
| FUNASA | 250 | Sem documentos |
| SESU | 246 | Fichas sintéticas |
| DNIT | 220 | 198 sem documentos; 22 não confirmadas |
| SETEC | 58 | Fichas sintéticas |
| CAIXA | 50 | Sem documentos |
| SIMEC-Outros | 24 | Fichas sintéticas |
| MIDR | 8 | Fichas sintéticas |
| Total | 6.783 | 6.263 só sintéticas, 498 sem docs, 22 não confirmadas |

SISMOB + SIMEC concentram 87,38% do grupo. A falta de causa/documentos está concentrada por fonte; não é prudente presumir ausência aleatória nem avaliar um classificador apenas no subconjunto fácil como se representasse o universo.

### Situação administrativa não é causa física
Entre os 6.783, a situação original contém 3.499 OBRA CANCELADA, 887 EM CANCELAMENTO, 449 LICITAÇÃO e 62 CONTRATAÇÃO. Há ainda planejamento e não iniciadas. Esses valores não provam abandono nem falta de recursos. Preservar a situação padronizada atual, mas registrar subgrupo administrativo e examinar se houve início físico e qual evento interrompeu o empreendimento. Alterar a definição do desfecho físico exigiria decisão metodológica posterior; não realizar isso implicitamente na recuperação.

## 2. Corrigir a proveniência antes de ampliar a coleta

**Achado concreto no código:** `src/main.py:89–98` extrai parte de num. instrumento como seq para DNIT; `src/main.py:111–120` faz operação análoga para CODEVASF. `src/extractors/pncp.py:83–86` reutiliza o mesmo seq nas rotas de compras e contratos. Isso não constitui resolução da identidade PNCP.

O manual oficial distingue sequencial gerado no PNCP, número do contrato, número do processo e número de controle. Portanto, não se deve assumir que o número local do contrato é o sequencial PNCP. O trecho de código é comprovado; atribuir cada vínculo errado a ele é hipótese que exige auditoria caso a caso. [Manual PNCP](https://pncp.gov.br/manual/pt-br/latest/contrato_empenho/consultar_contratos_ou_empenhos_de_uma_contratacao.html).

**Ação proposta P0:** resolver entidade oficial por identificador PNCP/CIPI, órgão/unidade, número/ano do contrato ou processo e objeto/município. Separar IDs de compra e contrato. Aceitar vínculo só com chave oficial consistente e contexto corroborante; conflito ou busca apenas por nome permanece candidato. Auditar os 22 casos DNIT antes de usá-los para causa. Não remover/reprocessar corpus inteiro nesta avaliação; marcar candidatos inválidos para correção explícita futura.

**Outro achado:** `src/extractors/tecnicos.py` gera PDFs a partir das linhas da planilha, alguns com títulos/textos que aparentam laudos oficiais. O banco corretamente os marca como ficha_sintetica. Reexecutar esse gerador não acrescenta evidência causal. Propor identificar claramente novas fichas como síntese gerada e preservar originais já hashados até migração/reprocessamento explícito. Metadado de tipo TERMO_COMPROMISSO não torna o arquivo original.

O rank atual de coleta favorece editais/projetos. Para recuperar causa factual, priorizar termos de paralisação, vistorias, relatórios de fiscalização/auditoria, justificativas de suspensão/rescisão, medições e correspondências. Editais e contratos com cláusulas condicionais não comprovam que o evento aconteceu.

## 3. Duas frentes de trabalho

### Frente A — causas presentes (3.181)
Os maiores grupos são: dificuldade técnica da executora (674), contrato rescindido (610), Outros (461), discricionariedade do gestor público (386), fato não previsto (244), discricionariedade ministerial (214), irregularidades da gestão anterior (121) e dificuldade financeira da executora (98).

Revisar primeiro os 674 casos técnicos: há argumento semântico para classe 1, mas a política atual os reserva por sobreposição com falhas da contratada. Formalizar o critério do agente/causa, examinar amostra por fonte e obter adjudicação antes de mudar a regra para todo o grupo. Examinar também desconformidade de execução (61) e falha de serviços (52). Isso pode ampliar cobertura sem milhares de novas buscas, mas não é ganho garantido nem autorização automática de uma nova classe.

Contrato rescindido (610) é resultado administrativo: atribuir 3 somente se evidência mostrar abandono/desistência/falha pertinente da contratada. Dificuldade financeira da executora (98) não equivale automaticamente a atraso de repasse (2) ou abandono (3). Outros/gestão/clima/judicial exigem contexto; causa comprovada fora das três categorias deve receber marcador auxiliar fora_taxonomia e continuar sem classe no modelo atual. Não alterar o campo de classe para 4.

Para múltiplas causas, preservar todas como evidências auxiliares e atribuir causa principal apenas quando explicitamente sustentada. Sem prioridade factual, manter ambiguidade; não escolher o maior código.

### Frente B — recuperar causas ausentes (6.783)
Fluxo obrigatório:
1. Identificar obra/contrato/proposta e data-base; separar aquisição em 2026 da data do documento histórico.
2. Consultar fonte do órgão responsável e recuperar documento original. Documento coletado hoje pode ser histórico; texto escrito em 2026 não deve substituir a evidência exigida até a data-base de 2025.
3. Verificar identidade, data e ocorrência factual. Texto sobre o que acontecerá SE a contratada abandonar não é abandono ocorrido.
4. Extrair trecho literal, página/offset, motivo, fonte/hash, revisor e justificativa. IA pode localizar e estruturar candidatos; não autoriza classe por confiança autodeclarada.
5. Adjudicar 1/2/3 e importar pelo fluxo revisado existente. Não preencher a coluna original da planilha com inferência; guardar causa recuperada e referência separadamente em artefato de revisão.
6. Sem prova, manter NULL e um motivo operacional específico: fonte_nao_localizada, acesso_indisponivel, identidade_inconclusiva, documento_sem_causa, evidencia_fora_corte, multicausal ou fora_taxonomia. São estados auxiliares propostos, não classes novas nem alteração já aplicada ao esquema.

## 4. Fontes oficiais por base

- **SISMOB:** iniciar pelo [SISMOB Cidadão](https://www.gov.br/pt-br/servicos/fiscalizar-obras-com-recursos-do-ministerio-da-saude-sismob-cidadao), resolver proposta/CNPJ/município e localizar histórico. A existência de consulta pública não garante acesso público a toda justificativa; se faltar, registrar lacuna e preparar solicitação ao órgão, sem envio automático.
- **SIMEC/FNDE:** o [monitoramento oficial](https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/programas/par/monitoramento) informa que Obras 2.0 registra ordens de serviço, cronogramas, vistorias e documentos. Usar [consulta pública](https://simec.mec.gov.br/painelObras/) para identidade e disponibilidade histórica. Para SESU/SETEC/SIMEC-Outros, confirmar órgão gestor/universidade/instituto; não presumir cobertura pelo FNDE.
- **CAIXA/FUNASA/MIDR:** testar [Transferegov Acesso Livre](https://www.gov.br/transferegov/pt-br/sistemas/acesso-livre) pela identidade do instrumento quando aplicável e o portal do órgão gestor; preferir acompanhamento/fiscalização à simples coleta do edital.
- **DNIT:** primeiro corrigir identidade; depois portal do órgão, processo e registros contratuais oficiais/PNCP vinculados corretamente.
- **Obrasgov/CIPI:** fonte complementar de cruzamento de identidade. O [portal oficial anuncia uma nova API](https://www.gov.br/obrasgov/pt-br/ferramentas-de-gestao-e-transparencia/api-de-dados-abertos-obrasgov-br_novo); validar integração atual no piloto, sem assumir disponibilidade de causas/documentos históricos de todas as obras.

Páginas oficiais consultadas em 29/09/2026. Pesquisa verificou rotas de acesso e contratos conceituais; não foi realizado teste de download para cada obra nem comprovada cobertura histórica desses portais.

## 5. Piloto proposto: 82 casos, antes da escala

**Lote de auditoria:** todos os 22 DNIT já com documentos (36 documentos; 13 obras com trechos candidatos). Verificar vínculos, datas e fatos; registrar descartes. Esse lote é de conveniência, não amostra representativa do universo.

**Lote de nova recuperação:** 60 obras sem fonte utilizável: SISMOB 24, SIMEC 16, FUNASA 5, DNIT 5 (das 198 sem documentos), CAIXA 4, SESU 2, SETEC 2, SIMEC-Outros 1 e MIDR 1. Seleção aleatória reproduzível dentro de base, ordenação prévia por id_fato e semente 42; inspecionar cobertura das situações originais e registrar reposições. Não escolher apenas obras de maior valor ou casos de fácil acesso. Amostra serve para viabilidade, não estimativa precisa de prevalência.

Medir por base: obras tentadas, identidade confirmada, documento original no corte, causa recuperada, classe adjudicada, divergências entre revisores, tempo por caso e motivo de insucesso. Fazer segunda revisão de todos os rótulos candidatos no piloto, por pessoa distinta quando disponível; sem segundo revisor, registrar revisão única, não inventar concordância.

**Regra operacional proposta:** até duas rotas oficiais e 15 minutos de busca manual inicial por obra; esgotamento vira pendência de coleta, nunca rótulo forçado. Medir tempo real e ajustar orçamento. Não enviar solicitações a terceiros sem instrução do pesquisador.

**Decisão de escala:** exigir 100% dos rótulos aceitos com identidade, fonte, corte e trecho verificados. Avaliar separadamente o rendimento causal: como referência inicial de orçamento, uma base com pelo menos 10 tentativas e >=20% de causas sustentadas pode justificar segundo lote; abaixo disso, rever rota antes de aumentar volume. Esse limiar é proposta de gestão de esforço, não garantia estatística nem critério de verdade. Bases com amostras menores precisam ampliar diagnóstico antes de concluir inviabilidade. Qualquer vínculo aceito erroneamente exige corrigir a resolução de identidade e reavaliar o lote.

## 6. Uso no aprendizado de máquina

Manter dois conceitos separados: estado administrativo conhecido e causa desconhecida. Proposta futura opcional: alvo binário derivado da situação em dataset separado, com nome explícito e auditoria da diferença entre situação administrativa e paralisação física. Não substituir silenciosamente o objetivo multiclasse do PCC. Mesmo em modelo binário, não usar situação/situação_origem como preditores do alvo derivado delas.

No treinamento causal 0–3, usar somente rótulos admissíveis e informar cobertura por fonte/classe; não afirmar generalização às 6.783 obras sem causa. A concentração de ausências e a origem distinta dos zeros por situação versus causas revisadas podem produzir viés de seleção. Preservar teste humano independente por obra; ajustar pesos/splits apenas após congelar exemplos. Causa original, causa recuperada, justificativas, fichas sintéticas e textos que revelem o desfecho exigem separação do conjunto de atributos para previsão antecipada. Classificação retrospectiva de causa não comprova predição de paralisação.

Se futuramente avaliar pseudo-rótulos ou supervisão fraca, guardar label_predita separada e versão/confiança calibrada; não sobrescrever label_risco factual nem contaminar teste. Não é a primeira opção enquanto identidade documental e fontes originais são o principal gargalo.

## 7. Resultado desta avaliação

Recomendação escolhida: corrigir vínculo documental, revisar catálogo de causas presentes e executar piloto pequeno estratificado de recuperação; expandir pelo rendimento observado. Nenhuma nova classe foi atribuída, nenhum corpus alterado, nenhum treinamento ou coleta massiva executado. Não é necessário repetir os 178 testes para alterações exclusivamente documentais; esse número permanece evidência da execução de 28/09, não nova regressão de hoje.
