# Tarefas: Primeira etapa da Sprint 4 (Card 8)

## Fase 1: Fundação
- [x] T001 Atualizar fechamento documental da Sprint 3 e registrar plano da Sprint 4.
- [x] T002 Criar especificação, pesquisa, modelo de dados, contrato e plano Speckit.
- [x] T003 Registrar baseline do banco e revisão/modelo candidato.

## Fase 2: Gate de comprimento
- [x] T004 Implementar auditoria integral com tokenizers E5/GTE fixados, sem truncamento ou escrita.
- [x] T005 Executar auditorias de ambos e avaliar distribuição/excedentes.

## Fase 3: Piloto técnico
- [x] T006 Preparar ambiente isolado e testar inferência/modelo em amostra determinística.
- [x] T007 Implementar persistência transacional/idempotente e validar em banco isolado.
- [x] T008 Executar piloto operacional pequeno e conferir integridade e proveniência.

## Fase 4: Decisão
- [x] T009 Avaliar consultas revisadas, vazão, memória e espaço; decidir escala/índice.
- [x] T010 Registrar validação e executar convergência Speckit.

T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010. Falha em gate impede a etapa dependente e deve ser registrada, sem vetorização integral automática.

## Phase 5: Convergence

- [ ] T011 Homologar relevância no universo dos pacotes locais de 2025/2026, registrar revisor e julgamentos, executar métricas e fechar a avaliação semântica de T009 conforme FR-006 / SC-004 (partial, HIGH).
- [x] T012 Complementar o custo exploratório de T009 com benchmark representativo dos comprimentos e espaço livre verificado no volume PostgreSQL, registrando orçamento para escala conforme FR-006 / plan: decisão de escala (partial, HIGH).

Execução de 2026-09-19: T012 concluída com auditoria integral e benchmark ponderado.
T011 avançou com revisão assistida por IA dos 125 conteúdos, 12 consultas e
comparação dos recortes; homologação humana permanece pendente. T009 mantém
decisão de não ampliar a carga diante da recuperação fraca de evidências causais.

## Phase 6: Convergence

- [ ] T013 Adjudicar com revisor humano os julgamentos assistidos e casos ambíguos dos pacotes locais, registrar tipo/autoria e recalcular métricas antes de homologar T011, conforme FR-006 / SC-004 (partial, HIGH).
- [ ] T014 Completar o ensaio de recuperação de T009 com proveniência original confirmada e positivos de risco no universo de avaliação; verificar a evidência documental antes de qualquer alteração de origem e manter snapshots de 2026 separados, conforme FR-006 / plan: piloto semântico / Constituição I-II (partial, HIGH).

## Decisão técnica posterior — 2026-09-23
T009 encerrada quanto à decisão de escala/índice: o usuário autorizou a carga integral, executada e validada na feature 009; busca exata mantida após medição. T011/T013/T014 permanecem pendências metodológicas explícitas, sem alegação de revisão humana ou proveniência original confirmada. A conclusão técnica da Sprint 4 não representa homologação dessas tarefas de pesquisa.
