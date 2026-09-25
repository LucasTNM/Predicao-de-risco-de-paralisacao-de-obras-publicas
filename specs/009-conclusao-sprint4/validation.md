# Validação final — Sprint 4 / feature 009

**Estado:** aprovação técnica após carga integral, em 2026-09-23.
Relatório completo: [report.md](report.md).

| Requisito / critério | Evidência | Resultado |
|---|---|---|
| FR-001 / SC-001: reauditoria | baseline_gpu.json; 157 recomputados | Aprovado |
| FR-002 / SC-002: corpus integral sem truncamento | manifesto e cobertura_final.json; 185.789/185.789 | Aprovado |
| FR-003: atomicidade e retomada | testes PostgreSQL; retomada com 185.789 reusos e zero gravações | Aprovado |
| FR-004 / SC-003: preservação | final_cpu.json; cinco fingerprints iguais, zero inconsistências e rótulos nulos | Aprovado |
| FR-005 / SC-004: busca e filtros | busca_final_textual.json; 8 autocorrespondências vetoriais + 8 textuais, 9 consultas e smoke CLI | Aprovado |
| FR-006: custo e índice | 55 min 46 s; CUDA pico 3,42 GiB; mediana SQL 177,5 ms; busca exata mantida | Aprovado |
| FR-007 / SC-005: testes e documentação | 96 testes; report.md; docs/Sprints/Sprint4.md | Aprovado |

## Reprodução e integridade
Amostra final de 64 conteúdos recomputada em CPU, cobrindo ano/origem/faixas WordPiece e extremos textuais. Todos compatíveis; maior erro absoluto 6,4381e-7. A cobertura estrutural e os hashes de conteúdo foram conferidos em todos os 185.789 chunks.

## Histórico operacional
A execução começou com Docker indisponível. Após recuperação, 94 testes completos passaram; a suíte evoluiu para 96 com a auditoria final e seus testes. A carga terminou sem erro. O Docker estava desligado quando a conferência final foi solicitada; foi iniciado novamente, e as verificações operacionais foram reexecutadas com sucesso. Nenhum volume foi resetado.

## Limites do aceite
A conclusão da feature 009 não marca como aprovadas as pendências científicas da 007. Homologação humana, rótulos e treinamento permanecem fora do aceite técnico solicitado.

T015 executada: a autocorrespondência foi ampliada para entrada textual completa, com 8/8 casos aprovados. Regressão final: **96 passed in 6.80s**, registrada em `logs/sprint4_009_regressao_final.txt`.

## Convergência Spec Kit final
Após corrigir T015 e executar a autocorrespondência textual, a nova avaliação não encontrou lacunas acionáveis. Conferidos 7 requisitos, 5 critérios de sucesso, 3 histórias, decisões técnicas do plano e 4 princípios constitucionais. As 15 tarefas estão concluídas. A convergência não acrescentou uma fase vazia; a atualização dos marcadores foi feita no encerramento da implementação.


## Revisão Spec Kit — 2026-09-24

Resultado: converged, sem novas tarefas técnicas. Conferidos 7 FR, 5 SC, 3 histórias, decisões de arquitetura do plano e 4 princípios da constituição contra implementação e evidências finais. Zero achados missing/partial/contradicts/unrequested no escopo 009; tasks.md preservado. Nenhum hook de extensão presente.

Manutenção documental posterior à convergência: docs/Sprints/Sprint4.md, docs/TCC_Dev_Diary.md e docs/referencias/Backlog.txt atualizados; docs/Proximos_Passos.md criado com pesquisa em fontes oficiais e sequência proposta. T011/T013/T014 de 007 permanecem científicas e abertas, sem inventar homologação humana.

Limitação desta revisão: engine Docker indisponível mesmo após solicitação de inicialização do Desktop; não foi repetida auditoria ao vivo nem regressão PostgreSQL. Evidências quantitativas/testes permanecem os registrados em 2026-09-23. Não houve alteração de código ou dados.

### Verificação antes do commit — 2026-09-24

Docker voltou a disponibilizar PostgreSQL saudável. O runner oficial `scripts/testar_sprint3.py` foi reexecutado em banco temporário isolado: **96 passed in 7.43s**, incluindo integração real. A execução sem configuração de integração registrou separadamente 74 aprovados e 22 ignorados; não substitui o resultado do runner oficial. Esta verificação atualiza a situação operacional acima, sem afirmar nova auditoria integral dos embeddings de produção. Documentos em `docs/` permanecem locais conforme `.gitignore`; especificações e relatório em `specs/` integram o commit.
