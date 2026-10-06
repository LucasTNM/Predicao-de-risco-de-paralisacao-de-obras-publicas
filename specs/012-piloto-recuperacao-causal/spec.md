# Feature Specification: Piloto de recuperação causal

**Feature Branch**: `codex/sprint5-rotulagem` (checkout existente)
**Created**: 2026-09-29
**Status**: Especificado; execução autorizada pelo pesquisador
**Input**: Executar o roadmap de recuperação causal da feature 011 usando SpecKit.

## User Scenarios & Testing
### User Story 1 — Identidade documental confiável (Priority: P1)
Como pesquisador, preciso impedir que documentos de contratos diferentes sejam usados como evidência de uma obra.
**Independent Test**: número local não autoriza download; identificador oficial confirmado autoriza somente sua espécie de registro.
**Acceptance Scenarios**:
1. Dado um instrumento local, nenhuma sequência oficial é presumida.
2. Dado identificador oficial, instituição, instrumento e objeto devem ser compatíveis antes de aceitar vínculo; ambiguidade vai para quarentena lógica com motivo.
3. Os 22 casos legados são examinados com os respectivos documentos, preservando arquivos e vínculos históricos.

### User Story 2 — Piloto rastreável (Priority: P1)
Como pesquisador, preciso medir recuperação possível antes de ampliar coleta.
**Independent Test**: selecionar 60 casos novos sem repetição, reproduzir seleção e registrar tentativas reais separadamente dos 22 legados.
**Acceptance Scenarios**:
1. Mesma população e semente 42 produzem os mesmos casos independentemente da ordem de entrada.
2. Toda obra recebe tentativa específica ou impedimento verificável; página inicial não conta como evidência recuperada.
3. Reinício preserva resultados anteriores e não duplica registros; indisponibilidade não significa inexistência da causa.

### User Story 3 — Revisão e escala (Priority: P2)
Como pesquisador, preciso separar causa desconhecida, hipótese e evidência aceita.
**Independent Test**: ausência, fonte sintética, data posterior e identidade incerta não geram rótulo; relatório discrimina rendimento por fonte.
**Acceptance Scenarios**:
1. Revisar amostra de dificuldade técnica da executora, desconformidade, falha de serviços e rescisão; declarar autoria e conflitos entre classes sem inventar homologação humana.
2. Aceitar candidato exige fonte, identidade, data até a data-base e trecho causal verificáveis; segunda revisão só com revisor disponível.
3. Decisão de escala usa ao menos 10 tentativas específicas e 20% de recuperação causal como limiar operacional provisório, sem extrapolar amostras pequenas.
4. Exportar registro por obra/data-base com pendência separada do estado administrativo e partição por identidade, distinguindo reserva futura de gold validado.

### Edge Cases
Identificador ausente ou com ano; homônimos; compra e contrato com sequências iguais; login com HTTP200; documentos compartilhados; causa múltipla; cancelamento sem início físico; fonte atual sem histórico; indisponibilidade; população menor que cota; arquivo alterado na retomada.

## Requirements
### Functional Requirements
- **FR-001**: Bloquear vínculo baseado apenas em sequência do instrumento; validar instituição, instrumento e objeto, separando compra/contrato.
- **FR-002**: Auditar 22 legados e gerar quarentena lógica por vínculo com motivo/evidência, preservando corpus/banco.
- **FR-003**: Manifestar 22 legados mais 60 novos: SISMOB24, SIMEC16, FUNASA5, DNIT5, CAIXA4, SESU2, SETEC2, SIMEC-Outros1, MIDR1. Ordenar identidades, semente42, representar situações originais dentro das cotas.
- **FR-004**: Consultar fontes oficiais por caso, até duas rotas e 15 minutos de esforço inicial por obra; registrar impedimentos e identificadores insuficientes.
- **FR-005**: Persistir respostas/tentativas atomicamente com hash, URL, parâmetros, horário, duração e estado; permitir retomada verificável.
- **FR-006**: Revisar catálogo/candidatos com autoria declarada, sem imputação ou edição de políticas históricas. Importar decisão apenas com identidade, fonte, data e trecho comprovados.
- **FR-007**: Relatar tentativas, documentos, identidades e causas confirmadas por base/coorte, esforço, limitações e decisão de expansão/suspensão.
- **FR-008**: Preservar rótulos não adjudicados, registrar pendências sem classe4, reservar avaliação por identidade e não treinar.
- **FR-009**: Testar correção/isolamento histórico, auditar banco, atualizar sprint e executar converge.

### Key Entities
Caso (obra/data-base, fonte, estado original, coorte, identificadores, impressão da fonte); tentativa (consulta, resposta, duração, estado); revisão (documento/obra, identidade, data, trecho, autor, decisão); resultado (indicadores e decisão de escala).

## Success Criteria
- **SC-001**: 82 casos únicos, todos com resultado ou impedimento explícito.
- **SC-002**: Nenhum vínculo novo por sequência isolada; todos os 22 legados auditados.
- **SC-003**: Todo rótulo aceito tem evidência histórica verificável; zero mudança por ausência ou texto sintético.
- **SC-004**: Retomada e indicadores reproduzíveis; nenhum dado de2026 rotulado.

## Assumptions
Inclui coleta pública limitada; exclui contato com órgãos, credenciais novas, coleta massiva, treino ou migração de corpus. Acesso bloqueado é resultado do piloto, não causa recuperada. Sem segundo revisor humano disponível: declarar revisão do assistente. Políticas v1/v2 imutáveis. Reserva de teste não equivale a gold homologado.
