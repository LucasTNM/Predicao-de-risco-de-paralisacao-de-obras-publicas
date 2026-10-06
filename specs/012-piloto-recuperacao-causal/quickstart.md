# Validação
Docker ativo e .env local. Executar da raiz:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pncp_identity.py tests/test_recovery_pilot.py -q
.\.venv\Scripts\python.exe scripts/piloto_recuperacao.py preparar
.\.venv\Scripts\python.exe scripts/piloto_recuperacao.py coletar
.\.venv\Scripts\python.exe scripts/piloto_recuperacao.py relatar
```
Esperado: 22+60 casos, respostas/impedimentos explícitos, relatórios por base, nenhuma escrita de rótulos. Repetir coletar reutiliza respostas íntegras; arquivos adulterados falham. Testes de rede usam fixtures, execução real é registrada separadamente.

Após mudança de implementação, executar `coletar --reprocessar` para recalcular resultados usando o cache, preservando os anteriores em historico_resultados/. Sem essa opção, reuso com hash de código diferente falha. `relatar` valida implementação/manifesto/respostas e aplica revisoes_identidade.json se presente; revisões exigem autor, justificativa, fonte e trecho verificáveis.

Integração real: `python scripts/testar_sprint3.py` cria e remove somente banco descartável tcc_test_*. Não usar o banco de produção como destino de testes. A auditoria de produção é somente leitura e compara os registros com populacao.json.
