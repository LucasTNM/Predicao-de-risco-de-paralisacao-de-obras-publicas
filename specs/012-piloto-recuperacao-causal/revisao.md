# Revisão do piloto e catálogo

Coleta: 2026-09-29. Consolidação e validação: 2026-09-30. Autor: assistente Codex. Não houve revisão humana nem concordância entre dois revisores medida.

## Catálogo

PCC §2.4.2, página PDF17, distingue deficiência técnica de projeto/capacidade institucional, fluxo de repasses/contrapartida e abandono da contratada. Não fornece tabela literal exaustiva para as causas da planilha. Revisadas cinco observações de cada grupo abaixo, 25 no total, com situação original, fonte e impressão da observação preservadas em `logs/piloto_recuperacao/revisao_catalogo.json`.

| Causa | Total pendente no inventário | Decisão da amostra |
| --- | ---: | --- |
| Dificuldade técnica da empresa executora | 674 | Não equiparar automaticamente à incapacidade institucional nem a abandono; obter descrição do mecanismo |
| Execução em desconformidade com o projeto | 61 | Distinguir erro de projeto, erro executivo e responsabilização da contratada |
| Falha na execução de serviços | 52 | Falha não comprova abandono; manter aberta a fronteira entre classes1/3 |
| Contrato Rescindido | 610 | Buscar motivação da rescisão; desfecho administrativo não define causa |
| Dificuldade financeira da empresa executora | 98 | Não confundir finanças da empresa com repasse público; comprovar eventual abandono |

Decisão: nenhum dos25 recebe novo rótulo com o texto disponível. Não editar v1/v2 nem criar v3 só para elevar cobertura. A resolução científica dessas fronteiras exige uma regra de adjudicação documentada; a presente análise declara a ambiguidade em vez de inventar consenso.

## Documentos legados

Os36 arquivos ligados às22 obras DNIT tiveram hashes verificados e seus objetos examinados. Os objetos não correspondem às obras: equipamentos/serviços administrativos, energia, locação, veículos e inscrições em eventos foram associados a obras rodoviárias. Trechos, hashes, motivo por vínculo e autoria estão em `revisoes_identidade.json` e `quarentena_vinculos.json` no diretório local do piloto.

Quarentena lógica no relatório/dataset auxiliar:36 vínculos excluídos como evidência causal deste piloto. Arquivos, embeddings e ponte original no PostgreSQL não foram alterados. Consultas antigas ao corpus não passam automaticamente por esta quarentena; antes de usar documentos para treino, aplicar a exclusão e ampliar a auditoria da origem PNCP. Isso não autoriza concluir que todos os documentos PNCP do corpus são incompatíveis.

## Novas consultas

- SISMOB:24 identidades por número exato de proposta + município/UF; `dsJustificativa` ausente em todas. Atualização/estado corrente não substitui causa histórica.
- Obrasgov/Transferegov:4 projetos localizados por instrumento→CIPI. Um passou comparação automática conservadora; três tiveram contexto de objeto, município/UF e repassador revisado pelo assistente. Os quatro históricos consultados estavam vazios. Cadastro atual pode ser de2026; serve para descoberta de identidade, não rótulo histórico.
- SIMEC:16 formulários barrados por reCAPTCHA; seis instrumentos também foram procurados no crosswalk público, sem correspondência. Não houve consulta individual ao painel concluída.
- Outros casos:5 instrumentos sem CIPI e11 sem identificador compatível com as rotas implementadas. Impedimento não significa inexistência de documento na instituição.

Nenhum candidato causal histórico elegível resultou dessas consultas; não havia decisão causal a importar. O importador de revisão existente continua sendo o caminho para evidências futuras, com autoria, hash, trecho e corte temporal, após verificação substantiva da identidade.

## Decisão de escala

Não ampliar a mesma rota SISMOB para milhares de casos:24/24 identidades, mas0/24 justificativas. Priorizar uma fonte histórica complementar antes de repetir consulta em massa. Para SIMEC, resolver acesso legítimo à consulta individual; nas bases pequenas, diagnosticar identificadores e rotas da instituição, sem extrapolar inexistência de causa. Os22 legados são amostra de conveniência, separados dos60 novos.

A reserva por base+id_tcu contém5.669 observações de2025; desenvolvimento contém22.619. Trata-se de reserva determinística preliminar, não gold homologado. Duplicatas físicas com identificadores diferentes ainda exigem reconciliação antes de treino. Situação, causa e metadados de revisão do registro auxiliar não estão aprovados como atributos preditivos. Treinamento e benchmark não foram executados.
