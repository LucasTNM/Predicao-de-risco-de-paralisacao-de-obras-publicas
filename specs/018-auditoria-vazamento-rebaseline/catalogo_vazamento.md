# Catálogo de Vazamento de Alvo e Inventário de Campos Textuais

**Feature:** 018-auditoria-vazamento-rebaseline  
**Data:** 2026-10-19  
**Auditoria:** Inspeção estrutural somente leitura sobre o acervo de 14.709 chunks de fichas sintéticas de 2025 (`tcc.dim_documento` com `origem_documento = 'ficha_sintetica'`).

---

## 1. Contexto e Diagnóstico

As fichas sintéticas foram geradas na Sprint 2/3 pelo módulo `tecnicos.py` para suprir a ausência de APIs públicas abertas de download de PDFs de projetos executivos nas bases SISMOB (Saúde), SIMEC/SESU/SETEC (Educação) e CODEVASF/MIDR (ver ADR-006 do Diário de Bordo).

A inspeção direta dos chunks no PostgreSQL revelou o seguinte formato padrão:

```text
MINISTÉRIO DA EDUCAÇÃO - FNDE
SIMEC - Sistema Integrado de Monitoramento Execução e Controle
Relatório Técnico de Fiscalização de Obras da Educação (PAR)
Identificador SIMEC: SESU-10594
Termo de Compromisso / PAR: nan
Empreendimento: UFVJM - Restaurante Universitário
Localização / Município: Diamantina/MG
Órgão Concedente: Ministério da Educação
Situação no FNDE: Paralisada (Origem: PARALISADA)           <-- [ALERTA DE VAZAMENTO CRÍTICO]
Evolução Física: 31.9% | Execução Financeira: 44.9%
Valor Previsto: R$ 1,898,382.90 | Valor Repassado: R$ 852,582.03
Laudo e ficha técnica de acompanhamento emitida para auditoria de contratos de engenharia e obras.
```

---

## 2. Inventário de Campos e Decisões Metodológicas

| Campo | Exemplo no Texto | Classificação de Risco | Decisão de Mascaramento | Justificativa |
| :--- | :--- | :---: | :---: | :--- |
| **Cabeçalho Institucional** | `MINISTÉRIO DA EDUCAÇÃO - FNDE`, `SIMEC...`, `CODEVASF...` | Neutro | **MANTER** | Contexto de domínio que identifica a tipologia do órgão gestor. |
| **Identificador do Sistema** | `Identificador SIMEC: SESU-10594` | Neutro | **MANTER** | Metadado cadastral sem correlação direta com o status de paralisação. |
| **Termo de Compromisso** | `Termo de Compromisso / PAR: nan` | Neutro | **MANTER** | Metadado contratual. |
| **Objeto do Empreendimento** | `Empreendimento: UFVJM - Restaurante Universitário` | Neutro | **MANTER** | **Conteúdo textual legítimo**: descreve o tipo de obra (escola, creche, restaurante, hospital, pavimentação), essencial para aprendizado semântico. |
| **Localização / Município / UF** | `Localização / Município: Diamantina/MG` | Neutro | **MANTER** | Contexto geográfico. |
| **Órgão Concedente** | `Órgão Concedente: Ministério da Educação` | Neutro | **MANTER** | Contexto administrativo. |
| **Situação / Status da Obra** | `Situação no FNDE: Paralisada (Origem: PARALISADA)` ou `Situação Contratual: Em execução (Origem: EM EXECUCAO)` | **CRÍTICO: VAZAMENTO DIRETO** | **REMOVER TOTALMENTE** | **Violação do Art. I da Constituição**: O texto declara explicitamente a variável dependente (`label_risco`), transformando a tarefa em memorização trivial de palavras-chave. |
| **Evolução Física / Financeira** | `Evolução Física: 31.9% \| Execução Financeira: 44.9%` | Moderado | **MANTER (ou Mascarar)** | Já existe nas colunas tabulares numéricas (`exec_fisica`, `exec_financeira`). No texto, não declara a paralisação diretamente, mas será avaliado no rebaseline. |
| **Valores Financeiros** | `Valor Previsto: R$ 1,898,382.90 \| Repassado: R$ 852,582.03` | Neutro | **MANTER** | Já existe nas colunas tabulares numéricas. |
| **Rodapé Fixo** | `Laudo e ficha técnica de acompanhamento...` | Ruído sintético | **REMOVER** | Texto boilerplate idêntico em todas as fichas, sem valor discriminativo. |

---

## 3. Especificação do Algoritmo de Mascaramento (Cenário C3)

Para o cenário C3 (Fichas Sintéticas Mascaradas):
1. **Regra de Remoção de Linha de Situação**:
   Qualquer linha iniciada por `Situação no ...:`, `Situação Contratual:` ou que contenha expressões como `(Origem: PARALISADA)`, `(Origem: EM EXECUÇÃO)`, `(Origem: CONCLUÍDA)`, `(Origem: CANCELADA)` deve ser completamente expurgada do texto antes da tokenização e recálculo de embeddings.
2. **Poda de Termos Residuais**:
   Garantir via regex que expressões como `paralisad`, `em execu`, `conclu` não permaneçam em nenhuma seção sintética.
3. **Preservação**:
   O texto remanescente preservará estritamente o cabeçalho, o nome do empreendimento, o município e os valores monetários.

---

## 4. Auditoria de Contadores de Metadados (Cenário C1 vs. C0)

Além do texto, os atributos tabulares abaixo foram identificados como **proxies artificiais de vazamento da Classe 1 (Deficiência Técnica)**:
- `has_embedding` (Falso para 98,8% das obras da Classe 1)
- `num_docs_validos` (0 para 98,8% das obras da Classe 1)
- `num_chunks_validos` (0 para 98,8% das obras da Classe 1)

**Decisão para C1, C2 e C3**:
Essas 3 colunas são removidas da matriz tabular $X_{\text{tab}}$, deixando apenas atributos cadastrais reais (`valor_investimento`, `valor_desbloqueado`, `exec_fisica`, `exec_financeira`, `base_cat`, `uf_cat`).
