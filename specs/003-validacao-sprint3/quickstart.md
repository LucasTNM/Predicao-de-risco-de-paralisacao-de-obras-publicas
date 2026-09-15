# Validação reproduzível (PowerShell)

Executar na raiz do repositório. Python e todas as dependências estão em `.venv`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\specify.exe version
$env:SPECIFY_FEATURE_DIRECTORY = 'specs/003-validacao-sprint3'
.\.specify\scripts\powershell\check-prerequisites.ps1 -Json -RequireSpec -RequireTasks -IncludeTasks
.\.venv\Scripts\pytest.exe
```

Os testes de banco são skipped sem TEST_DATABASE_URL; isso não é homologação
de integração. Para testar com PostgreSQL 17/pgvector local já provisionado:

```powershell
.\.venv\Scripts\python.exe scripts\testar_sprint3.py
```

O runner usa as configurações locais sem exibir senhas, cria um banco com UUID,
executa testes e remove exclusivamente o banco que criou. Requer o serviço
PostgreSQL ativo, usuário administrativo com CREATEDB e usuário tcc_app existente.

O DDL é aplicável via psql, mas a assinatura exigida pelo aplicativo é registrada
por `--modo schema`. Não executar psql e depois assinar o estado encontrado como
se estivesse homologado; um esquema manual precisa de comparação/migração explícita.

Com o corpus montado, preflight sem escrita no banco e inspeção do banco atual:

```powershell
.\.venv\Scripts\python.exe -m src.main --modo carga --ano 2025 --dry-run
.\.venv\Scripts\python.exe -m src.main --modo validar-banco
```

Consultar [validation.md](validation.md) para evidências desta revisão. Os números
esperados são relativos ao cenário, não uma promessa de volume integral carregado.

Reinicialização da governança, somente quando necessário:

```powershell
.\.venv\Scripts\specify.exe init --here --integration agy --script ps --non-interactive --force --ignore-agent-tools
```

`--force` mescla scaffolding: revisar diffs e preservar a constituição existente.
No Antigravity, usar `/speckit-constitution`, `/speckit-specify`, `/speckit-plan`,
`/speckit-tasks`, `/speckit-implement`, `/speckit-converge`. Neste trabalho as
skills e scripts foram executados pelo agente; a UI do Antigravity não foi testada.
