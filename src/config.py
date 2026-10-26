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

try:
    from dotenv import load_dotenv
except ImportError:  # Permite a Camada 1 operar antes da instalação opcional da LLM.
    def load_dotenv(*args: object, **kwargs: object) -> bool:
        return False

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DE ANO-BASE E DIRETÓRIOS
# ─────────────────────────────────────────────────────────────────────────────

# Ano-base do painel de obras
ANO_BASE = "2025"

# Diretório raiz do projeto local (onde o código é executado)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Carrega credenciais locais sem expô-las no código-fonte. O arquivo .env é ignorado pelo Git.
load_dotenv(ROOT_DIR / ".env")

# Caminho raiz obrigatório no Google Drive (Windows)
BASE_DRIVE = Path(r"G:\Meu Drive\TCC_DOCUMENTOS")

# Particionamento anual de dados brutos no Drive (ex: G:\Meu Drive\TCC_DOCUMENTOS\2025_Dados_brutos)
PASTA_DADOS_BRUTOS = BASE_DRIVE / f"{ANO_BASE}_Dados_brutos"

# Particionamento anual de textos extraídos no Drive (ex: G:\Meu Drive\TCC_DOCUMENTOS\2025_Textos_extraidos)
PASTA_TEXTOS_EXTRAIDOS = BASE_DRIVE / f"{ANO_BASE}_Textos_extraidos"

# Arquivo consolidado de log de coleta de documentos no Drive
ARQUIVO_LOG_COLETA = PASTA_DADOS_BRUTOS / "log_coleta.csv"

# Arquivo consolidado de log de extração de texto no Drive
ARQUIVO_LOG_EXTRACAO = PASTA_TEXTOS_EXTRAIDOS / "log_extracao.csv"

# ─────────────────────────────────────────────────────────────────────────────
# CARD 5 — HIGIENIZAÇÃO NLP + LLM
# ─────────────────────────────────────────────────────────────────────────────

# A Camada 2 é opcional: sem chave ou SDK instalada, o pipeline preserva a
# higienização determinística da Camada 1 e registra a ocorrência no manifesto.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Modelo atual indicado pela API Gemini. Pode ser sobrescrito localmente no .env.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_RPM_LIMIT = 15
GEMINI_RPD_LIMIT = 1500
GEMINI_TEMPERATURA = 0.1

# Pastas multi-ano e limiar de acionamento seletivo da Camada 2.
ANOS_DISPONIVEIS = ["2025", "2026"]
ANOS_PAINEL_TCU = ["2022", "2023", "2024", "2025", "2026"]
PASTA_TEXTOS_LIMPOS = BASE_DRIVE / f"{ANO_BASE}_Textos_Limpos"
LIMIAR_SUJEIRA_LLM: float = 0.30

# Sprint 3: os caminhos anuais sao resolvidos pelo carregador em tempo de execucao.
TOKENIZER_NAME = os.getenv("TOKENIZER_NAME", "neuralmind/bert-base-portuguese-cased")
TOKENIZER_REVISION = os.getenv("TOKENIZER_REVISION", "94d69c95f98f7d5b2a8700c420230ae10def0baa")
CHUNKING_VERSION = os.getenv("CHUNKING_VERSION", "sliding-window-v1")

# ─────────────────────────────────────────────────────────────────────────────
# PARÂMETROS E CONSTANTES DE EXTRAÇÃO DE TEXTO & OCR (SPRINT 2)
# ─────────────────────────────────────────────────────────────────────────────

# Localização padrão dos binários nativos no Windows
TESSERACT_CMD = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
POPPLER_PATH = Path(r"C:\Users\lucas\AppData\Local\Programs\MiKTeX\miktex\bin\x64")

# Limiares de Decisão de Densidade (caracteres úteis / página)
LIMIAR_DENSIDADE_NATIVO: float = 200.0   # >= 200: Aceita extração nativa rápida
LIMIAR_DENSIDADE_PARCIAL: float = 50.0   # 50-199: OCR seletivo apenas em páginas vazias
LIMIAR_MIN_CHARS_TOTAL: int = 100       # < 100 total pós-OCR: IRRECUPERAVEL

# Resolução de renderização DPI para OCR
DPI_OCR_PADRAO: int = 200

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


def obter_pasta_dados_brutos(ano_base: str = ANO_BASE) -> Path:
    """Retorna a pasta de dados brutos no Google Drive para um ano-base específico."""
    return BASE_DRIVE / f"{str(ano_base).strip()}_Dados_brutos"


def obter_arquivo_log_coleta(ano_base: str = ANO_BASE) -> Path:
    """Retorna o caminho do log_coleta.csv no Google Drive para um ano-base específico."""
    return obter_pasta_dados_brutos(ano_base) / "log_coleta.csv"


def obter_planilha_origem(ano_base: str = ANO_BASE) -> Path:
    """Retorna o caminho da planilha local data_{ano_base}.xlsx."""
    return ROOT_DIR / f"data_{str(ano_base).strip()}.xlsx"


def obter_pasta_base(nome_base: str, ano_base: str = ANO_BASE) -> Path:
    """
    Retorna e garante a existência da pasta de partição da base no Google Drive.
    Exemplo: G:\\Meu Drive\\TCC_DOCUMENTOS\\2025_Dados_brutos\\dnit\\
    """
    pasta = obter_pasta_dados_brutos(ano_base) / nome_base.strip().lower()
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logging.getLogger("PipelineObras").warning(
            f"Não foi possível criar o diretório no Drive ({pasta}): {exc}. "
            "Verifique se o Google Drive está montado e sincronizado."
        )
    return pasta


def obter_pasta_textos_base(nome_base: str, ano_base: str = ANO_BASE) -> Path:
    """
    Retorna e garante a existência da pasta de partição de textos extraídos no Google Drive.
    Exemplo: G:\\Meu Drive\\TCC_DOCUMENTOS\\2025_Textos_extraidos\\dnit\\
    """
    pasta = BASE_DRIVE / f"{ano_base}_Textos_extraidos" / nome_base.strip().lower()
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logging.getLogger("PipelineObras").warning(
            f"Não foi possível criar o diretório de textos no Drive ({pasta}): {exc}. "
            "Verifique se o Google Drive está montado e sincronizado."
        )
    return pasta


def obter_pasta_textos_limpos_base(nome_base: str, ano_base: str = ANO_BASE) -> Path:
    """
    Retorna e garante a pasta de saída da higienização para uma base e ano-base.
    Exemplo: G:\\Meu Drive\\TCC_DOCUMENTOS\\2025_Textos_Limpos\\dnit\\
    """
    pasta = BASE_DRIVE / f"{ano_base}_Textos_Limpos" / nome_base.strip().lower()
    try:
        pasta.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logging.getLogger("PipelineObras").warning(
            f"Não foi possível criar o diretório de textos limpos no Drive ({pasta}): {exc}. "
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
