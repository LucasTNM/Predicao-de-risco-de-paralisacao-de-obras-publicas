# -*- coding: utf-8 -*-
"""
src/utils.py
============
Funções utilitárias de I/O, deduplicação de logs em memória O(1),
travas de idempotência de download e integração de validação de documentos.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import logging
from pathlib import Path
import re
import threading
from typing import Any
import unicodedata

from src.inspect_pdf import avaliar_pdf, inspect_pdf, sha256_file
from src.config import ARQUIVO_LOG_COLETA, logger
from src.multiformato import (
    MIN_CHARS_UTEIS_GATEKEEPER,
    TERMOS_EMAIL_IMEDIATOS,
    TERMOS_VITAIS_WHITELIST_PRIORITARIA,
    detectar_comprovante_email,
)

# Lock de concorrência para escrita segura de logs em execuções paralelas (ThreadPool)
_LOCK_CSV = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE CURADORIA NLP / FILTRO DE QUALIDADE DOCUMENTAL
# ─────────────────────────────────────────────────────────────────────────────

# Whitelist prioritária: documentos vitais de engenharia, licitação e execução contratual
_WHITELIST_TERMOS = list(TERMOS_VITAIS_WHITELIST_PRIORITARIA)

# Blacklist: termos que indicam ruído burocrático quando não acompanhados de termo vital da whitelist
_BLACKLIST_TERMOS = [
    "e-mail", "email", "comprovante", "leitura", "encaminhamento",
    "publicação", "publicacao", "despacho", "recibo",
    "confirmação", "confirmacao", "notificação", "notificacao",
    "protocolo de envio", "aviso de recebimento",
    "outlook", "enc:", "fw:", "re:",
]

# Limite mínimo de caracteres para um documento ser considerado denso (Gatekeeper >= 800 chars)
_MIN_CHARS_UTEIS = MIN_CHARS_UTEIS_GATEKEEPER

# Sufixos das fichas sintéticas legadas geradas por FPDF na Sprint 1
SUFIXOS_FICHAS_SINTETICAS = (
    "_FichaTecnica_Saude.pdf",
    "_FichaTecnica_FNDE.pdf",
    "_Relatorio_Tecnico.pdf",
)


def eh_ficha_sintetica_legada(nome_arquivo: str) -> bool:
    """Identifica se um arquivo de log refere-se a uma ficha sintética FPDF legada."""
    nome = (nome_arquivo or "").strip()
    return any(nome.endswith(suf) or suf in nome for suf in SUFIXOS_FICHAS_SINTETICAS)


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES DE CURADORIA: FILTRO PRÉ-DOWNLOAD, DEDUP SHA-256 E PODA
# ─────────────────────────────────────────────────────────────────────────────

def filtro_pre_download_dom(texto_dom: str) -> tuple[bool, str]:
    """
    BARREIRA 1 — INTERCEPTAÇÃO PRÉ-DOWNLOAD (DOM/HTML E METADADOS API):
    1. Rejeita extensões pesadas de CAD/mídia/planilha (.dwg, .xlsx, .mp4, .rar),
       mas PERMITE pacotes `.zip` e documentos `.pdf`, `.docx`, `.odt`, `.rtf`;
    2. Bloqueia imediatamente cabeçalhos explícitos de e-mail / protocolo de leitura;
    3. Prioriza `_WHITELIST_TERMOS` (Termos Aditivos, Memoriais, Projetos Básicos,
       Pareceres Técnicos, Rescisões, Paralisações, Vistorias, Contratos, Editais),
       impedindo falsos negativos quando o título contiver palavras como "publicação" ou "despacho";
    4. Aplica `_BLACKLIST_TERMOS` aos demais itens sem termo vital.

    Retorna (deve_baixar: bool, motivo: str).
    """
    texto_lower = texto_dom.strip().lower()

    if not texto_lower:
        return True, "texto_dom_vazio"

    # Rejeita extensões binárias de CAD/planilha/mídia se explícitas no link
    for ext_proibida in (".dwg", ".dxf", ".mp4", ".avi", ".xlsx", ".xls", ".csv", ".rar"):
        if texto_lower.endswith(ext_proibida) or f"{ext_proibida} " in texto_lower:
            return False, f"BLACKLIST[{ext_proibida}]"

    # 1. Bloqueio imediato de e-mails explícitos e avisos de leitura
    for termo_email in TERMOS_EMAIL_IMEDIATOS:
        if termo_email in texto_lower:
            return False, f"BLACKLIST[{termo_email}]"

    # 2. Whitelist prioritária de engenharia e execução contratual
    for termo in _WHITELIST_TERMOS:
        if termo in texto_lower:
            return True, f"WHITELIST[{termo}]"

    # 3. Blacklist geral para despachos/publicações/notificações sem termo vital
    for termo in _BLACKLIST_TERMOS:
        if termo in texto_lower:
            return False, f"BLACKLIST[{termo}]"

    # 4. Se for pacote .zip, libera para inspeção cirúrgica in-memory
    if ".zip" in texto_lower:
        return True, "WHITELIST[.zip]"

    # Default: permite download para avaliação pelo Gatekeeper Pós-Download
    return True, "DEFAULT_PERMITIDO"


def verificar_duplicata_sha256(
    caminho_pdf: Path,
    id_obra: str,
    cache_hashes: dict[str, set[str]],
) -> tuple[bool, str]:
    """
    BARREIRA 2 — DEDUPLICAÇÃO CRIPTOGRÁFICA IN-MEMORY:
    Calcula o SHA-256 do arquivo e verifica se já existe um hash idêntico
    associado à mesma id_obra no cache em memória.

    Retorna (eh_duplicata: bool, hash_sha256: str).
    """
    try:
        file_hash = sha256_file(caminho_pdf)
    except Exception:
        return False, ""

    obra_hashes = cache_hashes.setdefault(id_obra, set())

    if file_hash in obra_hashes:
        return True, file_hash

    obra_hashes.add(file_hash)
    return False, file_hash


def validar_densidade_textual(
    caminho_pdf: Path,
    min_chars: int = _MIN_CHARS_UTEIS,
) -> tuple[bool, int, bool]:
    """
    BARREIRA 3 — PODA DE BAIXA DENSIDADE E GATEKEEPER ANTI-LIXO:
    Abre o PDF recém-baixado, extrai texto nativo e verifica:
    1. Se possui texto extraível;
    2. Se não é um comprovante de envio de e-mail (`De:`, `Para:`, `Assunto:`, `Enviado em:`);
    3. Se atinge a densidade mínima exigida (`>= 800` caracteres em produção).

    Retorna (aprovado: bool, total_chars: int, texto_extraivel: bool).
    """
    try:
        insp = inspect_pdf(caminho_pdf)
    except Exception:
        return False, 0, False

    texto_extraivel = insp["text"]["extractable"]
    total_chars = insp["text"]["total_chars"]

    if not texto_extraivel:
        return False, total_chars, texto_extraivel

    texto_amostra = " ".join(
        str(item.get("text") or "") for item in (insp.get("sample", {}).get("text") or [])
    )
    eh_email, _ = detectar_comprovante_email(texto_amostra)
    if eh_email:
        return False, total_chars, texto_extraivel

    if total_chars < min_chars:
        return False, total_chars, texto_extraivel

    return True, total_chars, texto_extraivel


# Cabeçalho padrão do log de coleta
COLUNAS_LOG = [
    "timestamp",
    "base_de_dados",
    "id_obra",
    "num_instrumento",
    "empreendimento",
    "nome_arquivo",
    "tamanho_bytes",
    "paginas",
    "texto_extraivel",
    "tipo_documento",
    "vinculo_federal",
    "relacao_obra",
    "status_validacao",
    "confianca",
    "observacoes",
]


def normalizar_coluna(col: Any) -> str:
    """
    Remove acentos, converte para minúsculas e remove espaços das colunas.
    """
    if not isinstance(col, str):
        return str(col)
    return unicodedata.normalize("NFKD", col).encode("ASCII", "ignore").decode("ASCII").lower().strip()


def arquivo_ja_existe_valido(caminho: Path) -> bool:
    """
    TRAVA DE IDEMPOTÊNCIA:
    Verifica se o arquivo já existe no disco/Drive e se seu tamanho é superior a 0 bytes.
    """
    try:
        return caminho.exists() and caminho.is_file() and caminho.stat().st_size > 0
    except Exception:
        return False


def inicializar_log_csv(caminho_csv: Path = ARQUIVO_LOG_COLETA) -> None:
    """
    Inicializa o arquivo CSV consolidado no Google Drive caso ele não exista.
    """
    try:
        if not caminho_csv.exists():
            caminho_csv.parent.mkdir(parents=True, exist_ok=True)
            with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(COLUNAS_LOG)
            logger.info(f"Log CSV inicializado com sucesso em: {caminho_csv}")
    except Exception as exc:
        logger.error(f"Erro ao inicializar arquivo de log CSV ({caminho_csv}): {exc}")


def carregar_chaves_log_existentes(caminho_csv: Path = ARQUIVO_LOG_COLETA) -> dict[tuple[str, str, str], str]:
    """
    DEDUPLICAÇÃO DE LOGS O(1):
    Lê o CSV consolidado e carrega em memória um dicionário O(1) mapeando:
    (base_de_dados.lower(), id_obra.strip(), nome_arquivo.strip()) -> status_validacao
    Garantindo consulta instantânea O(1), retorno do status real em cache hits
    e compatibilidade total com operadores 'in'.
    """
    chaves_existentes: dict[tuple[str, str, str], str] = {}

    if not caminho_csv.exists():
        return chaves_existentes

    try:
        with open(caminho_csv, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                base = (row.get("base_de_dados") or "").strip().lower()
                id_obra = (row.get("id_obra") or "").strip()
                nome_arq = (row.get("nome_arquivo") or "").strip()
                status = (row.get("status_validacao") or "VALIDADO").strip().upper()
                if base and nome_arq:
                    chaves_existentes[(base, id_obra, nome_arq)] = status
        logger.info(f"Deduplicação de Log: {len(chaves_existentes)} registros carregados em memória O(1).")
    except Exception as exc:
        logger.warning(f"Não foi possível ler chaves do log CSV existente ({caminho_csv}): {exc}")

    return chaves_existentes


def carregar_obras_concluidas(
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
    ignorar_fichas_sinteticas: bool = True,
) -> set[tuple[str, str]]:
    """
    PULO O(1) NO NÍVEL DO PIPELINE:
    Retorna um conjunto de tuplas (base_de_dados.lower(), id_obra.strip()) para todas
    as obras que já possuem ao menos um documento AUTÊNTICO com status VALIDADO ou
    VALIDADO_COM_RESSALVAS no log CSV.
    Quando `ignorar_fichas_sinteticas=True` (padrão), fichas FPDF sintéticas legadas
    não contam como obra concluída, permitindo recoleta de documentos autênticos.
    """
    obras_ok: set[tuple[str, str]] = set()

    if not caminho_csv.exists():
        return obras_ok

    try:
        with open(caminho_csv, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = (row.get("status_validacao") or "").strip().upper()
                nome_arq = (row.get("nome_arquivo") or "").strip()
                if ignorar_fichas_sinteticas and eh_ficha_sintetica_legada(nome_arq):
                    continue
                if status in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
                    base = (row.get("base_de_dados") or "").strip().lower()
                    id_obra = (row.get("id_obra") or "").strip()
                    if base and id_obra:
                        obras_ok.add((base, id_obra))
        logger.info(
            f"Cache de obras concluídas ({caminho_csv.parent.name}): "
            f"{len(obras_ok)} obras com documentos autênticos carregadas em memória O(1)."
        )
    except Exception as exc:
        logger.warning(f"Não foi possível carregar cache de obras concluídas ({caminho_csv}): {exc}")

    return obras_ok


def registrar_log_documento(
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    base: str,
    id_obra: str,
    num_inst: str,
    emp: str,
    nome_arq: str,
    tamanho: int,
    paginas: int,
    extraivel: bool,
    tipo_doc: str,
    vinc_fed: str,
    rel_obra: str,
    status_val: str,
    confianca: str,
    obs: str = "",
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
) -> bool:
    """
    Registra um novo documento no CSV se e somente se ele ainda não constar no cache O(1).
    Utiliza Thread Lock para garantir escrita thread-safe em processamento concorrente.
    Retorna True se gravado, ou False se pulado por duplicidade.
    """
    chave = (base.strip().lower(), str(id_obra).strip(), str(nome_arq).strip())

    if chave in cache_log:
        return False

    with _LOCK_CSV:
        if chave in cache_log:
            return False
        try:
            inicializar_log_csv(caminho_csv)
            with open(caminho_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.datetime.now().isoformat(),
                    base,
                    id_obra,
                    num_inst,
                    emp,
                    nome_arq,
                    tamanho,
                    paginas,
                    extraivel,
                    tipo_doc,
                    vinc_fed,
                    rel_obra,
                    status_val,
                    confianca,
                    obs,
                ])
            if isinstance(cache_log, dict):
                cache_log[chave] = status_val
            elif isinstance(cache_log, set):
                cache_log.add(chave)
            return True
        except Exception as exc:
            logger.error(f"Falha ao registrar documento no log CSV ({nome_arq}): {exc}")
            return False


def validar_e_registrar_pdf(
    caminho_pdf: Path,
    base_nome: str,
    id_obra: str,
    num_inst: str,
    emp: str,
    obs_extra: str,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
) -> dict[str, Any]:
    """
    Executa a validação NLP / estrutural via inspect_pdf e faz o registro seguro no log.

    OTIMIZAÇÃO: Verifica o cache O(1) ANTES de abrir o PDF pela rede do Google Drive.
    Se o documento já estiver registrado no log, retorna o status validado original
    sem incorrer em I/O de disco/rede para reextrair texto do PDF.
    """
    chave = (base_nome.strip().lower(), str(id_obra).strip(), caminho_pdf.name.strip())

    if chave in cache_log:
        status_gravado = cache_log.get(chave, "VALIDADO") if isinstance(cache_log, dict) else "VALIDADO"
        logger.debug(f"    [CACHE HIT] Documento já registrado ({status_gravado}): {caminho_pdf.name}. Pulando revalidação de PDF.")
        return {
            "validation": {
                "result": status_gravado,
                "document_type": "CACHED",
                "federal_link": "CACHED",
                "relation_to_public_work": "CACHED",
                "confidence": "CACHED",
            },
            "inspection": {
                "file": {"size_bytes": 0},
                "pdf": {"pages": 0},
                "text": {"extractable": False},
            },
        }

    avaliacao = avaliar_pdf(caminho_pdf)
    val_data = avaliacao["validation"]
    insp = avaliacao["inspection"]

    registrar_log_documento(
        cache_log=cache_log,
        base=base_nome,
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        nome_arq=caminho_pdf.name,
        tamanho=insp["file"]["size_bytes"],
        paginas=insp["pdf"]["pages"],
        extraivel=insp["text"]["extractable"],
        tipo_doc=val_data["document_type"],
        vinc_fed=val_data["federal_link"],
        rel_obra=val_data["relation_to_public_work"],
        status_val=val_data["result"],
        confianca=val_data["confidence"],
        obs=obs_extra,
        caminho_csv=caminho_csv,
    )

    return avaliacao
