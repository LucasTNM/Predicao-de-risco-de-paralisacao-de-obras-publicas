# Roadmap proposto — recuperação causal

Proposta de 2026-09-29, não execução autorizada de coleta massiva. Detalhes, fontes e critérios: avaliacao-pendencias-20260929.md. Esta lista não substitui tasks.md da feature 011, que permanece concluído em seu escopo técnico.

1. P0 / identidade: em futura feature, especificar resolvedor PNCP/contrato separado, evidência de vínculo e quarentena de documentos incompatíveis. Arquivos candidatos: src/main.py, src/extractors/pncp.py e testes de identificação. Critério: nenhum vínculo aceito só por seq extraído do instrumento; contratos/compra distintos.
2. P1 / catálogo: adjudicar amostra de dificuldade técnica da executora, desconformidade e falha de serviços; distinguir rescisão genérica de abandono. Entregável: protocolo e decisões assinadas/declaradas; alteração de política exige versão nova e simulação, nunca edição de v1/v2.
3. P1 / piloto: manifestar 22 casos existentes + 60 novas buscas estratificadas (semente 42), fonte/data/identidade, tentativas e orçamento. Entregáveis locais propostos: manifesto_piloto.json e resultados_piloto.json; os arquivos ainda não foram gerados.
4. P1 / fontes: adaptar recuperação de originais SISMOB/SIMEC e testar Transferegov/órgãos para bases pertinentes; não gerar ficha sintética como sucesso causal. Registrar ausência de acesso/causa/corte.
5. P1 / revisão: duas revisões dos candidatos quando houver revisores disponíveis; importar somente prova datada e vinculada; conflitos permanecem NULL. Revisor não pode ser inventado pelo agente.
6. P2 / decisão de escala: comparar rendimento/custo por fonte; expandir só rota que demonstrar acesso e evidência. Amostras pequenas não sustentam conclusão de inviabilidade da base.
7. P2 / dataset: registrar causa desconhecida separada de estado administrativo; congelar gold de teste e documentar viés de seleção. Treino não integra esta avaliação.

Todos os itens estão propostos e não executados. Coleta e implementação seguintes devem passar por novos artefatos SpecKit, mantendo histórico das features 010/011.

**Atualização 30/09/2026:** execução autorizada posteriormente e realizada na [feature012](../012-piloto-recuperacao-causal/report.md); esta página preserva a proposta original. Piloto concluído com impedimentos explícitos e sem novas causas; validação PostgreSQL final pendente de Docker.
