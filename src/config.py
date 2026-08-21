# -*- coding: utf-8 -*-
"""
src/config.py
=============
Módulo central de configuração, variáveis de ambiente, caminhos do Google Drive (Windows)
e logging rotativo para o pipeline de predição de risco de obras públicas.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE ANO-BASE E DIRETÓRIOS
# ─────────────────────────────────────────────────────────────────────────────

# Ano-base do painel de obras
ANO_BASE = "2025"

# Diretório raiz do projeto local (onde o código é executado)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Caminho raiz obrigatório no Google Drive (Windows)
BASE_DRIVE = Path(r"G:\Meu Drive\TCC_DOCUMENTOS")

# Particionamento anual de dados brutos no Drive (ex: G:\Meu Drive\TCC_DOCUMENTOS\2025_Dados_brutos)
PASTA_DADOS_BRUTOS = BASE_DRIVE / f"{ANO_BASE}_Dados_brutos"

# Arquivo consolidado de log de coleta de documentos no Drive
ARQUIVO_LOG_COLETA = PASTA_DADOS_BRUTOS / "log_coleta.csv"

# Arquivos de entrada e executáveis locais
PLANILHA_ORIGEM = ROOT_DIR / f"data_{ANO_BASE}.xlsx"
DRIVER_PATH = ROOT_DIR / "msedgedriver.exe"
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ARQUIVO_LOG_SISTEMA = LOGS_DIR / "sistema.log"

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES INSTITUCIONAIS E LIMITES
# ─────────────────────────────────────────────────────────────────────────────

CNPJ_DNIT = "04892707000100"
CNPJ_CODEVASF = "00399857000126"

# Limite configurável de obras coletadas por base (None para execução completa em produção)
LIMITE_OBRAS_POR_BASE: int | None = None

# Bases de dados suportadas no painel
BASES_SUPORTADAS = [
    "dnit",
    "caixa",
    "funasa",
    "codevasf",
    "simec",
    "sismob",
    "sesu",
    "setec",
    "simec-outros",
    "midr",
]

# Headers padrão de requisições HTTP
DEFAULT_HEADERS = {
    "User-Agent": "TCC-Auditoria-ObrasGov/1.0 (Audit-Pipeline-MLOps)",
    "Accept": "application/json, text/plain, */*",
}


def obter_pasta_base(nome_base: str) -> Path:
    """
    Retorna e garante a existência da pasta de partição da base no Google Drive.
    Exemplo: G:\\Meu Drive\\TCC_DOCUMENTOS\\2025_Dados_brutos\\dnit\\
    """
    pasta = PASTA_DADOS_BRUTOS / nome_base.strip().lower()
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logging.getLogger("PipelineObras").warning(
            f"Não foi possível criar o diretório no Drive ({pasta}): {exc}. "
            "Verifique se o Google Drive está montado e sincronizado."
        )
    return pasta


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE LOGGING ROTATIVO
# ─────────────────────────────────────────────────────────────────────────────

def configurar_logger(nome: str = "PipelineObras") -> logging.Logger:
    """
    Configura logger com RotatingFileHandler (5MB, 3 backups) e saída no console (UTF-8).
    """
    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = RotatingFileHandler(
            ARQUIVO_LOG_SISTEMA,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


logger = configurar_logger()
