# CLI extension
`python scripts/rotular_sprint5.py recuperar --output logs/sprint5_recuperacao.json` executa leitura consistente e exporta pacote de paralisadas de 2025 sem causa (NULL/vazio/hífen/Não informado). Não altera rótulos nem causa original. --write não é aceito para recuperar. Saída atômica sem sobrescrita e exit codes existentes.
`aplicar`/`inventariar` passam a usar v2; `auditar` aceita v1/v2; `revisar` mantém prova documental quando decisão for humana. Outputs indicam método regra_situacao ou regra/revisao.
