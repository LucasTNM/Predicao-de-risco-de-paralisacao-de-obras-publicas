# Quickstart: 014-dataset-particoes-quarentena

**Feature**: [spec.md](spec.md)

Este guia apresenta as instruções para executar e validar a extração de dados, a agregação vetorial com quarentena e o particionamento estratificado sem vazamento de obras.

## 1. Pré-requisitos

Garantir que o ambiente Python e o PostgreSQL local estão prontos:
```powershell
.\.venv\Scripts\python.exe scripts/preparar_docker.py
```

## 2. Execução da Preparação de Datasets

Executar a extração completa e o particionamento oficial:
```powershell
.\.venv\Scripts\python.exe scripts/preparar_dataset_sprint6.py --output-dir dados_processados/sprint6 --seed 42
```

Saída esperada:
- Criação dos 4 arquivos Parquet em `dados_processados/sprint6/`:
  - `dataset_treino_dev_2025.parquet`
  - `dataset_teste_retido_2025.parquet`
  - `dataset_pendentes_2025.parquet`
  - `dataset_isolado_2026.parquet`
- Criação do manifesto de governança:
  - `dados_processados/sprint6/manifesto_particionamento.json`
- Relato no terminal com `vazamento_detectado: false` e tempo de execução.

## 3. Validação Automatizada via Testes

Executar os testes específicos de integridade e não vazamento:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dataset_preparation.py -v
```

Cenários validados pelos testes:
- Interseção vazia de `id_tcu` entre partição de desenvolvimento e teste retido.
- Exclusão dos 36 documentos quarentenados da agregação vetorial.
- Preservação exata da cardinalidade de 28.288 observações de 2025 e 32.292 de 2026.
- Preservação da integridade dimensional (sem soma indevida de valores pela ponte N:N).
- Determinismo: execuções repetidas geram hashes idênticos.
