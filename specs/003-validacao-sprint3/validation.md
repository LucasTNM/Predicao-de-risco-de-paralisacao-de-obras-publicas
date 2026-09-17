# Validação da Sprint 3 — 2026-09-10

## Revisão de fechamento em 2026-09-17

- Escopo do novo commit: `.gitignore`, registros Spec Kit de fechamento e evidências
  da carga de 2026. Nenhuma alteração de código, testes, dependências ou DDL.
- Regras adicionadas: ambientes `.venv-*`, caches tox/nox/pip e dumps/estado local
  do PostgreSQL. `git ls-files -ci --exclude-standard` não encontrou arquivos
  rastreados que precisassem ser retirados do índice. SQL e governança preservados.
- Relatório visual local de oito páginas produzido em
  `docs/Relatorio_Sprints_2_e_3_Orientacao.pdf`, revisado página a página, com modelo,
  cardinalidades, chaves, proveniência, fragmentação, transações e limites científicos.
  O PDF, seu gerador, corpus, logs e credenciais permanecem ignorados.
- Seleção do índice exportada para `scratch/sprint3-review/` para testar o conteúdo
  da Sprint 3 sem incorporar modificações locais de embeddings da Sprint 4.
- Pytest sobre essa cópia: **43 passed, 13 skipped**, 8,22 s. Os 13 skips exigem
  PostgreSQL. A tentativa do runner de integração terminou antes dos testes por
  timeout de conexão; o Docker Desktop falhou na inicialização de seu socket local.
  A remoção desse socket foi bloqueada pela política de execução. A integração
  **não foi revalidada nesta revisão**; os 56 testes aprovados em 16/09 são históricos.
- Os testes de integração não foram afetados pelo novo diff, composto somente
  de documentação e regras de exclusão. Essa evidência não homologa novamente
  o banco operacional nem a carga integral.
- Conferência de escopo: FR-010 e FR-011 atendidos; seleção pronta para FR-012.
  Publicação autorizada na branch existente `codex/prontidao-carga`, sem merge
  em main. Alterações locais de código e artefatos da Sprint 4 ficam fora do commit.

## Evidência histórica da implementação

> **Atualização de 2026-09-16:** este relatório preserva a validação histórica
> do piloto de 45 documentos. A carga posterior do lote elegível foi concluída
> para 2025 e 2026, com 51.009 documentos e zero inconsistências; evidências em
> `specs/005-carga-documental-2025/validation.md` e
> `specs/006-carga-documental-2026/validation.md`. As 225 ocorrências de 2026
> permanecem fora do lote, sem homologação do acervo bruto integral.

## Parecer

Implementação e piloto validados após as correções abaixo. A carga integral não
está homologada: o banco contém o piloto de 45 documentos de 2025. Embeddings e
rótulos continuam pendentes, conforme os limites da Sprint 3.

## Spec Kit aplicado antes das correções

- specify-cli **1.0.6**, instalado somente na `.venv` e fixado em requirements.txt.
- Init oficial: `--here --integration agy --script ps --non-interactive --force
  --ignore-agent-tools`. O executável agy não estava no PATH; a integração foi
  gerada sem alterar o aplicativo Antigravity.
- **10 skills** com front matter YAML válido; inclui as seis solicitadas.
- Constituição **1.0.0**, com quatro artigos e rastreabilidade das nove ADRs.
- Fluxo executado: constitution → specify → plan → tasks → implement → converge.
  Resolvedores e scripts oficiais confirmaram os artefatos da feature.
- `.specify/`, `.agents/skills/` e `specs/` são versionáveis. `.env` e o ponteiro
  local `.specify/feature.json` permanecem ignorados. Nenhum commit foi criado.
- Teste da UI/invocação dentro do Antigravity não foi realizado. A primeira
  especificação exercitada é esta revisão da Sprint 3; Sprint 4 permanece futura.

## Defeitos reproduzidos e correções

| Requisito | Problema confirmado | Correção / evidência |
| --- | --- | --- |
| FR-005 | Preflight aprovava TXT inválido e PDF ausente/alterado | Validação física compartilhada; UTF-8, tamanho, qualidade e SHA-256 antes da elegibilidade |
| FR-005 | NaN ou metadados numéricos inválidos interrompiam a auditoria | Quarentena identificada por documento |
| FR-005/006 | Troca de TXT de mesmo tamanho após preflight não era detectada | Hash observado no preflight é revalidado antes da carga, inclusive com force |
| FR-006 | Reuso aceitava contagem correta com fato/offset/conteúdo incorreto | Comparação completa de ocorrências, texto, tokens e configuração |
| FR-003/004 | Auditoria aprovava corrupção de mesmo comprimento e intervalos deslocados | Recalcular hash dos chunks e conferir início, progresso, lacunas e IDs sobrepostos |
| FR-006 | Mudar apenas search_path causava falso drift | Assinatura calculada sob contexto fixo, restaurando a sessão |
| FR-008 | Falha de gravação do relatório era silenciosa; JSON podia ficar truncado | Temporário, flush/fsync e replace atômico; falha visível e relatório anterior preservado |
| FR-008 | pytest.exe não importava src; teste Gemini dependia da chave local | pythonpath explícito e mock da condição sem chave |
| FR-008 | Runner de banco executava somente testes unittest | Runner usa Pytest e inclui testes funcionais; restaura a variável de ambiente |

Os testes negativos falharam antes das correções. O teste adicional de rollback
simula colisão depois do início de COPY e confirma que nenhuma das três tabelas
documentais retém gravação parcial. O teste adicional de publicação de relatório
confirma que falha no replace mantém o JSON anterior legível.

## Execuções reproduzidas

| Execução | Resultado |
| --- | --- |
| Baseline anterior às correções | 29 passed, 6 skipped, 6,51 s |
| `.venv/Scripts/pytest.exe` após correções | **36 passed, 13 skipped**, 5,65 s |
| `.venv/Scripts/python.exe scripts/testar_sprint3.py` | **49 passed**, 6,86 s, sem skips/warnings |
| `python -m pip check` | Sem dependências quebradas |
| `git diff --check` | Sem erros de whitespace nas alterações rastreadas |
| YAML/constituição/artefatos Spec Kit | 10 skills válidas, constituição sem placeholders, artefatos presentes |

Os skips da execução simples são exclusivamente os 13 testes que exigem banco
isolado. O runner cria `tcc_test_<uuid>`, provisiona a extensão e executa testes
como tcc_app; remove somente a base criada. O PostgreSQL real estava em
`pgvector/pgvector:0.8.6-pg17-bookworm`. Nenhuma carga no banco operacional foi feita.

## Banco existente e piloto (somente leitura)

| Tabela | Linhas observadas |
| --- | ---: |
| dim_obra | 28.288 |
| fato_risco | 28.288 |
| dim_documento | 45 |
| dim_embedding | 205 |
| ponte_documento_embedding | 207 |

`--modo validar-banco` retornou `valido=true`, com zero inconsistências nas nove
verificações, incluindo os novos hashes e cobertura de tokens. Separadamente,
os **45 documentos** foram revalidados contra os PDFs/TXTs e retokenizados com
BERTimbau fixado, dentro de conexão `read_only=True`; todos retornaram
`reutilizado`. Isso testa a compatibilidade com as cargas anteriores sem escrita.

## Alcance e limites

A validação independente do banco detecta corrupção interna e cobertura parcial,
mas a prova completa dos offsets de caracteres e da cauda exige a fonte original.
O loader agora faz essa comparação no reuso; ela foi executada sobre todo o piloto.
Como contrapartida, reuso retokeniza cada documento em vez de confiar apenas nas
contagens. A geração de vetores, avaliação de embeddings, rótulos supervisionados
e prevenção de vazamento nos conjuntos futuros não foram implementadas nesta revisão.

O DDL original foi preservado. A aplicação homologada deve usar `--modo schema`;
execução manual via psql não registra a assinatura exigida pelo aplicativo e
demanda comparação/migração explícita, sem aceitar automaticamente o schema encontrado.

Resultados históricos de 51.009 documentos elegíveis não significam que todos
tenham sido carregados. A varredura física integral iniciada nesta revisão foi
encerrada após o progresso de pelo menos 2.000 dos 15.408 candidatos de 2025,
sem resultado consolidado anual e antes de auditar 2026. Ela extrapola a
validação de implementação/piloto e exige leitura de todo o corpus remoto;
**os volumes integrais de elegibilidade não foram re-homologados**. Nenhuma
fonte ou tabela operacional foi modificada. Para concluir essa etapa operacional,
executar o dry-run documentado no quickstart e aguardar o relatório final.

A leitura física agora usa cinco workers, em lotes de até dez documentos,
preservando ordem e quarentenas determinísticas. O teste com 13 fontes, incluindo
uma UTF-8 inválida, confirma igualdade entre execução serial e concorrente.
O CLI informa progresso a cada mil documentos. O relatório consolidado só fica
disponível ao concluir a auditoria, portanto progresso parcial não é aprovação.

## Convergência da revisão

Conferidos nove requisitos funcionais, quatro critérios de sucesso, sete cenários
de aceite e os quatro artigos da constituição, além das decisões do plano.
As correções, os testes, as skills e as evidências exigidos por esta feature estão
presentes. A limitação operacional do corpus está explicitada conforme FR-009 e
SC-004; ela não foi convertida em alegação de homologação integral.
