# -*- coding: utf-8 -*-
"""
src/parsers/exceptions.py
=========================
Hierarquia de exceções customizadas e decorators de resiliência (retry com backoff)
para o pipeline de parsing de PDFs e OCR em produção.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
import time
from typing import Any, Callable, TypeVar

# ─────────────────────────────────────────────────────────────────────────────
# HIERARQUIA DE EXCEÇÕES CUSTOMIZADAS
# ─────────────────────────────────────────────────────────────────────────────

class PdfParsingError(Exception):
    """Exceção base para todas as falhas no pipeline de parsing e OCR."""
    def __init__(self, message: str, caminho_pdf: Path | str | None = None) -> None:
        self.caminho_pdf = Path(caminho_pdf) if caminho_pdf else None
        super().__init__(message)


class PdfCorruptError(PdfParsingError):
    """Lançada quando a estrutura interna do PDF está corrompida ou o arquivo não é um PDF válido."""
    pass


class PdfEncryptedError(PdfParsingError):
    """Lançada quando o PDF está protegido por senha ou criptografado contra leitura."""
    pass


class PdfOcrFailError(PdfParsingError):
    """Lançada quando o OCR falha ou produz volume textual insuficiente (< 100 chars)."""
    pass


class PdfIOError(PdfParsingError):
    r"""Lançada em falhas persistentes de I/O de disco ou rede (Google Drive G:\)."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# DECORATOR DE RETRY COM BACKOFF EXPONENCIAL (I/O RESILIENCE)
# ─────────────────────────────────────────────────────────────────────────────

F = TypeVar("F", bound=Callable[..., Any])


def retry_on_io_error(
    max_retries: int = 3,
    base_delay: float = 2.0,
    backoff_factor: float = 2.0,
    logger_instance: logging.Logger | None = None,
) -> Callable[[F], F]:
    r"""
    Decorator para mitigar oscilações de I/O e latência de sincronização no Google Drive montado (G:\).

    Captura: OSError, PermissionError, IOError, FileNotFoundError.
    Estratégia: Executa até `max_retries` tentativas com espera exponencial (ex: 2s -> 4s -> 8s).
    Se todas as tentativas falharem, encapsula a exceção e levanta `PdfIOError`.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log = logger_instance or logging.getLogger("PipelineObras")
            delay = base_delay

            for tentativa in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (OSError, PermissionError, IOError, FileNotFoundError) as exc:
                    if tentativa == max_retries:
                        log.error(
                            f"[I/O ERRO DEFINITIVO] Função '{func.__name__}' falhou após {max_retries} tentativas: {exc}"
                        )
                        # Identifica caminho do arquivo se disponível nos argumentos
                        caminho = None
                        if args and isinstance(args[0], (str, Path)):
                            caminho = args[0]
                        elif "caminho_pdf" in kwargs:
                            caminho = kwargs["caminho_pdf"]
                        elif "caminho_txt" in kwargs:
                            caminho = kwargs["caminho_txt"]

                        raise PdfIOError(
                            f"Falha persistente de I/O em '{func.__name__}' após {max_retries} tentativas: {exc}",
                            caminho_pdf=caminho,
                        ) from exc

                    log.warning(
                        f"[I/O RETRY {tentativa}/{max_retries}] Erro transitório em '{func.__name__}': {exc}. "
                        f"Aguardando {delay:.1f}s (backoff)..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor

        return wrapper  # type: ignore

    return decorator
