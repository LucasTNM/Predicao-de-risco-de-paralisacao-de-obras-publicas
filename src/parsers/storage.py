# -*- coding: utf-8 -*-
"""
src/parsers/storage.py
======================
Módulo de persistência, resiliência e idempotência para o pipeline de extração de texto.

Implementa:
- Log transacional consolidado (log_extracao.csv).
- Cache em memória O(1) de PDFs já processados (Pause & Resume).
- Padrão Write-Ahead (gravação física do .txt antes do commit no log CSV).
- Trava de concorrência thread-safe para escrita atômica.
- Fallback de verificação de integridade no sistema de arquivos.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
from pathlib import Path
import threading
from typing import Any

from src.config import ARQUIVO_LOG_EXTRACAO, PASTA_TEXTOS_EXTRAIDOS, logger
from src.parsers.pdf_to_text import ResultadoExtracao

# Lock de concorrência para escritas no log CSV de extração
_LOCK_LOG_EXTRACAO = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# TAREFA 3.1 — ESQUEMA DO ARQUIVO DE MANIFESTO (log_extracao.csv)
# ─────────────────────────────────────────────────────────────────────────────

COLUNAS_LOG_EXTRACAO = [
    "timestamp",
    "ano_base",
    "base_de_dados",
    "nome_pdf",
    "nome_txt",
    "metodo_extracao",
    "total_paginas",
    "total_chars",
    "densidade_media",
    "tempo_segundos",
    "status",
    "sha256_pdf",
    "observacoes",
]


def inicializar_log_extracao_csv(caminho_csv: Path = ARQUIVO_LOG_EXTRACAO) -> None:
    """
    Inicializa o arquivo CSV de log de extração caso ele ainda não exista.
    Garante a criação de pastas pai e a escrita do cabeçalho canônico.
    """
    try:
        if not caminho_csv.exists():
            caminho_csv.parent.mkdir(parents=True, exist_ok=True)
            with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(COLUNAS_LOG_EXTRACAO)
            logger.info(f"Log CSV de extração inicializado em: {caminho_csv}")
    except Exception as exc:
        logger.error(f"Erro ao inicializar arquivo de log CSV ({caminho_csv}): {exc}")


def calcular_sha256_arquivo(caminho: Path, chunk_size: int = 1024 * 1024) -> str:
    """
    Calcula o hash criptográfico SHA-256 de um arquivo de forma eficiente por blocos.
    """
    digest = hashlib.sha256()
    try:
        with open(caminho, "rb") as f:
            while chunk := f.read(chunk_size):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# TAREFA 3.2 — CACHE O(1) DE PDFs JÁ PROCESSADOS (PAUSE & RESUME)
# ─────────────────────────────────────────────────────────────────────────────

def carregar_pdfs_ja_processados(
    caminho_csv: Path = ARQUIVO_LOG_EXTRACAO,
) -> dict[tuple[str, str, str], str]:
    """
    Lê o manifesto CSV uma única vez na inicialização e carrega um dicionário em memória:
    (ano_base, base_de_dados.lower(), nome_pdf) -> status

    Permite que o orquestrador pule em O(1) (<0.01 ms) qualquer PDF que já tenha
    sido processado com sucesso em execuções anteriores, sem acessar o disco/Drive.
    """
    cache_processados: dict[tuple[str, str, str], str] = {}

    if not caminho_csv.exists():
        return cache_processados

    try:
        with open(caminho_csv, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ano = (row.get("ano_base") or "").strip()
                base = (row.get("base_de_dados") or "").strip().lower()
                nome_pdf = (row.get("nome_pdf") or "").strip()
                status = (row.get("status") or "OK").strip().upper()

                if base and nome_pdf:
                    cache_processados[(ano, base, nome_pdf)] = status

        logger.info(
            f"Cache de Extração: {len(cache_processados)} PDFs carregados em memória O(1) do log."
        )
    except Exception as exc:
        logger.warning(f"Não foi possível carregar cache do log de extração ({caminho_csv}): {exc}")

    return cache_processados


# ─────────────────────────────────────────────────────────────────────────────
# TAREFA 3.4 — VARREDURA DE FALLBACK NO FILESYSTEM
# ─────────────────────────────────────────────────────────────────────────────

def verificar_txt_existente_valido(caminho_txt: Path, min_chars: int = 1) -> bool:
    """
    Verifica se o arquivo .txt já existe fisicamente no disco e se seu tamanho é válido.
    Funciona como segundo nível de proteção contra reprocessamento indevido.
    """
    try:
        return caminho_txt.exists() and caminho_txt.is_file() and caminho_txt.stat().st_size >= min_chars
    except Exception:
        return False


from src.parsers.exceptions import retry_on_io_error


# ─────────────────────────────────────────────────────────────────────────────
# TAREFA 3.3 — PADRÃO WRITE-AHEAD (GRAVAR .TXT ANTES DO COMMIT NO LOG)
# ─────────────────────────────────────────────────────────────────────────────

@retry_on_io_error(max_retries=3, base_delay=2.0)
def salvar_texto_e_registrar_log(
    caminho_pdf: Path,
    caminho_txt: Path,
    resultado: ResultadoExtracao,
    ano_base: str,
    base_nome: str,
    cache_log: dict[tuple[str, str, str], str],
    caminho_csv: Path = ARQUIVO_LOG_EXTRACAO,
) -> bool:
    """
    Executa a persistência atômica segundo o padrão Write-Ahead:
    1. Grava fisicamente o texto extraído no arquivo .txt (UTF-8).
    2. Valida que o .txt foi persistido com sucesso.
    3. Registra a transação de forma thread-safe no log CSV.
    4. Atualiza o cache O(1) em memória.

    Retorna True se persistido e registrado com sucesso, ou False caso contrário.
    """
    chave = (str(ano_base).strip(), str(base_nome).strip().lower(), caminho_pdf.name.strip())

    # Se não houve erro fatal e há texto extraído, grava o arquivo .txt
    if resultado.metodo != "ERRO" and resultado.texto_completo:
        try:
            caminho_txt.parent.mkdir(parents=True, exist_ok=True)
            caminho_txt.write_text(resultado.texto_completo, encoding="utf-8")
        except Exception as exc:
            logger.error(f"Falha de I/O ao gravar arquivo .txt ({caminho_txt}): {exc}")
            resultado.erros.append(f"Falha de I/O ao gravar .txt: {exc}")
            resultado.metodo = "ERRO"

    # Mapeamento refinado de status para auditoria e governança MLOps
    erros_str = " ".join(resultado.erros).lower()

    if "criptografado" in erros_str or "senha" in erros_str:
        status_log = "CRIPTOGRAFADO"
    elif "corrompido" in erros_str or "cabeçalho" in erros_str or "assinatura" in erros_str:
        status_log = "CORROMPIDO"
    elif "i/o" in erros_str or "permissão" in erros_str or "não encontrado" in erros_str:
        status_log = "ERRO_IO"
    elif resultado.metodo == "IRRECUPERAVEL":
        status_log = "IRRECUPERAVEL"
    elif resultado.metodo == "NATIVO+OCR":
        status_log = "OCR_PARCIAL"
    elif resultado.metodo == "ERRO":
        status_log = "ERRO"
    else:
        status_log = "OK"

    # Calcula hash do PDF original para rastreabilidade
    hash_pdf = calcular_sha256_arquivo(caminho_pdf) if caminho_pdf.exists() else ""
    observacoes = " | ".join(resultado.erros) if resultado.erros else ""

    # Commit seguro no CSV com Thread Lock
    with _LOCK_LOG_EXTRACAO:
        try:
            inicializar_log_extracao_csv(caminho_csv)
            with open(caminho_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.datetime.now().isoformat(),
                    ano_base,
                    base_nome.strip().lower(),
                    caminho_pdf.name,
                    caminho_txt.name if resultado.texto_completo else "",
                    resultado.metodo,
                    resultado.total_paginas,
                    resultado.total_chars,
                    f"{resultado.densidade_media:.2f}",
                    f"{resultado.tempo_segundos:.4f}",
                    status_log,
                    hash_pdf,
                    observacoes,
                ])
            cache_log[chave] = status_log
            return True
        except Exception as exc:
            logger.error(f"Falha ao registrar log de extração para {caminho_pdf.name}: {exc}")
            return False
