# CLI

- `auditar_proveniencia_sprint3.py`: leitura dos documentos ligados a embeddings
  preenchidos, hashes dos arquivos físicos, exportação em logs. Saída 0 se cadeia
  física íntegra, 2 se alguma falha; origem continua pendente quando não homologada.
- `gerar_embeddings_sprint4.py --limite 32 --ano 2025 --origem nao_confirmada [--write]`:
  congela até 32 pendentes por ID; default somente inferência, limite máximo 512.
- `gerar_embeddings_sprint4.py --retomar logs/<execucao>.json [--write]`:
  usa a mesma seleção/configuração, rejeita override; vetor compatível é reutilizado
  sem inferência. Não sobrescrever vetor incompatível ou conteúdo alterado.
- `--batch-size 8`: commit por lote; inferência interna batch 2; máximo 32.

Lote interrompido: checkpoint INTERROMPIDO, código não zero. Retomar o mesmo
manifesto confere o banco, inclusive se houve commit antes da falha no relatório.
Parâmetros/seleção têm checksum, sem alegar assinatura criptográfica de autoria.
