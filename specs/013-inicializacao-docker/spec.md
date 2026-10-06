# Feature Specification: Inicialização autônoma do Docker
**Feature Branch**: `codex/sprint5-rotulagem` (checkout existente)
**Created**: 2026-09-30
**Status**: Especificação validada
**Input**: Concluir a validação da sprint e abrir o Docker quando fechado, sem depender do pesquisador.

## User Scenarios & Testing
### User Story 1 — Retomar com Docker fechado (Priority: P1)
Ao executar um comando do projeto que usa o banco local, o pesquisador recebe ambiente iniciado e pronto.
**Independent Test**: partir do Desktop parado, iniciar autonomamente e alcançar PostgreSQL saudável, preservando observações/rótulos.
**Acceptance Scenarios**:
1. Ambiente fechado: solicitar início, apresentar progresso e conectar dentro do prazo configurado.
2. Ambiente aberto: reutilizar sem interrupção de outras tarefas.
3. Engine lento: aguardar com limite; erro específico se esgotar prazo.
### User Story 2 — Diagnosticar falhas (Priority: P2)
Receber diagnóstico quando aplicação estiver ausente ou inicialização falhar.
**Independent Test**: simular falhas e exigir encerramento limitado, mensagem sem credenciais e integridade do ambiente.
**Acceptance Scenarios**:
1. Falha de startup: registrar etapa/motivo e diagnóstico; não prometer reparo de defeitos internos do produto.
2. Banco remoto ou conexão explícita de teste: nenhuma inicialização de Desktop por tentativa de conexão.
3. Banco saudável e autenticação incorreta: erro de conexão, sem reinício da infraestrutura.
### Edge Cases
CLI/plugin ausente; instalação por usuário; contexto Linux diferente do padrão; contexto remoto; container parado/ausente; timeout; sailor-ingest.sock; falta de interface gráfica; conexões concorrentes.

## Requirements
### Functional Requirements
- **FR-001**: Iniciar Desktop por interface oficial e aguardar engine Linux, com orçamento total configurável e progresso.
- **FR-002**: Reutilizar engine/serviço saudável e iniciar apenas PostgreSQL deste projeto quando necessário.
- **FR-003**: Integrar ao runner de testes e à conexão padrão local; conexões explícitas/remotas não acionam inicialização.
- **FR-004**: Preservar contexto global, volumes, sockets, distribuições e configurações; não interromper automaticamente ambientes ativos.
- **FR-005**: Falhar por etapa/motivo sem credenciais; confirmar disponibilidade somente após engine e saúde do serviço.
- **FR-006**: Oferecer comando de preparação e instrução persistente para futuras sessões do assistente.
- **FR-007**: Validar reuso, timeout, falha, escopo local e startup real; executar regressões e atualizar documentos SpecKit/sprint.
### Key Entities
Estado do ambiente (engine, serviço, etapa, duração), tentativa e resultado de preparação, evidência do teste.

## Success Criteria
- **SC-001**: Desktop parado inicia autonomamente e PostgreSQL fica saudável em até240s no teste real, ou impedimento específico é documentado.
- **SC-002**: Ambiente saudável reutilizado sem comandos de inicialização; dados/rótulos preservados no teste real.
- **SC-003**: Timeout/erro encerram preparação dentro do orçamento; diagnósticos não revelam credenciais.
- **SC-004**: Testes/auditoria passam, evidências registradas e comandos do projeto preparam ambiente quando pertinente.

## Assumptions
Windows com Docker Desktop instalado e usuário autorizado. Rotina não substitui reparo administrativo de instalação defeituosa. Teste controlado com Desktop parado apenas após confirmar que o único container ativo pertence ao projeto e que não há cargas/testes em curso; a operação normal apenas inicia/reutiliza. Outros sistemas exigem engine já disponível.
