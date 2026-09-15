# Research — Sprint 3

## Decisão: scaffolding oficial agy, dependência fixa e estado local separado

Usar specify-cli 1.0.6 do PyPI oficial, instalado na `.venv`. O comando de versão
é `specify version`, não `python -m specify --version`. O init com `agy` falhou
por falta do executável no PATH e passou com `--ignore-agent-tools`. Foram
geradas skills e templates oficiais; não há hooks de extensões instalados.

Fontes: [instalação oficial](https://github.github.com/spec-kit/installation.html),
[fluxo oficial](https://github.github.com/spec-kit/quickstart.html) e help local 1.0.6.
Alternativa rejeitada: instalação global ou simulação manual da árvore de skills.

## Decisão: validar fontes antes da elegibilidade e novamente antes da carga

`audit_sources` apenas conferia presença de TXT, sem ler UTF-8, tamanho ou PDF.
Qualidade `NaN` interrompia o lote em vez de produzir quarentena. Compartilhar
validação evita divergência entre dry-run e carga. Guardar hash observado no
preflight permite detectar alterações posteriores de mesmo tamanho.
Alternativa rejeitada: considerar elegíveis arquivos até falharem na escrita.

## Decisão: retomada verifica conteúdo e ocorrências

`load_document` considerava assinatura e produto das contagens suficientes.
Uma alteração SQL nos offsets, tokens ou fato pode preservar essas contagens.
Comparar ocorrências esperadas e conteúdo canônico antes de reutilizar. O custo
adicional de retokenizar cada documento é aceito nesta auditoria de integridade;
uma futura otimização precisa preservar a mesma garantia.

## Decisão: assinatura estável sem migração silenciosa

A pesquisa independente de schema/validação foi delegada conforme speckit-plan.
O DDL usa SET LOCAL search_path=tcc,public, mas a validação usa a sessão externa;
fixar o contexto da consulta do catálogo. O teste em PostgreSQL real confirmou
o falso drift após mudar somente search_path. `.gitattributes` já força SQL em
LF; normalizar quebras de linha no hash é defesa adicional, não defeito observado.
Não alterar as cinco
tabelas, nem recalcular marcadores para aceitar estruturas desconhecidas.

## Decisão: evidências atômicas e testes herméticos

`run_load.save` sobrescrevia JSON diretamente e ocultava cinco falhas de I/O.
Usar temporário e replace; erro persistente deve ser visível. O runner de banco
descobria somente unittest: migrá-lo para Pytest inclui os novos testes funcionais.
O teste de fallback Gemini dependia de ausência de chave real; mockar a condição.

Baseline em 2026-09-10: 29 passed, 6 skipped em 6,51 s, com chave Gemini desativada
somente no processo e cache Pytest desativado. Integração exige PostgreSQL local;
Docker estava parado na inspeção inicial. Nenhuma falha foi ocultada como aprovação.

Reproduções negativas posteriores: cinco testes de preflight/relatório falharam;
o runner original registrou 43 testes, nove falhas de assertions e três erros
(incluindo subtests), abrangendo as falhas de integridade e search_path.
A execução direta de pytest.exe também falhou ao importar src; `pythonpath = .`
corrige a resolução. Cache foi movido para logs/pytest_cache porque a pasta
.pytest_cache existente recusava escrita, sem apagar ou alterar suas permissões.

O DDL executado diretamente via psql cria tabelas, mas não grava o marcador
de homologação usado pelo aplicativo. Usar `--modo schema` para o fluxo suportado;
adoção de schema manual exige comparação/migração explícita. Não alterar o SQL
existente somente para corrigir seu comentário, preservando seu hash homologado.
