# Pesquisa e decisões
- Manter GTE fixado: cabe em todos os185789chunks auditados anteriormente, sem alterar chunking. Revalidar no processamento. [Hugging Face](https://huggingface.co/Alibaba-NLP/gte-multilingual-base).
- Reutilizar modelo e submanifestos<=512: evita inicialização repetida e checkpoints gigantes. Pesquisa independente speckit-plan identificou bugs de filtro `sintetico`/`ficha_sintetica` e revisãoNULL; corrigir com testes.
- GPU em ambiente separado: hardware real RTX5060/driver616.56 suporta runtime disponível, wheel torch2.14.0+cu130 encontrado no índice oficial para cp314Windows. Comparar resultados antes da carga; manter CPU disponível. [Instalação oficial](https://pytorch.org/get-started/locally/).
- Busca exata tem recall técnico completo e filtros prévios; HNSW depende de medição, não é pré-requisito do objetivo. [pgvector](https://github.com/pgvector/pgvector).
- Distinguir conclusão técnica de homologação científica: pedido atual autoriza integral; limitações semânticas medidas em007 não desaparecem. Não inventar avaliação humana ou rótulos.
