# Contratos CLI
Auditoria: --recompute opcional, --device cpu|cuda, --output caminho; read-only; erro não zero se integridade/reprodução falhar.
Carga: --preparar ou --retomar caminho; --write necessário para gravar; preparação congela corpus completo; dispositivo/batch/threads congelados e sem override na retomada. Disco livre mínimo5GiB antes de iniciar; estadoINTERROMPIDO em falha. Subexecuções512, commitbatch32, inferênciabatch configurável1..32.
Busca: --consulta obrigatória; --ano2025|2026 opcional; --origem original|ficha_sintetica|nao_confirmada; --k1..100; mesmo modelo/revisão, CPUdefault, nenhum dado persistido. Resultado JSON inclui distâncias, texto e vínculos com documentos.

Auditoria final: `--baseline <auditoria-inicial.json>` faz a saída reprovar quando contagens ou fingerprints não vetoriais mudam. `--recompute --sample 64 --stratified` inclui ano, origem, faixas WordPiece e extremos textuais.
