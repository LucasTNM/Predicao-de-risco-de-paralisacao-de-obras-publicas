# -*- coding: utf-8 -*-
"""
src/extractors/pncp.py
======================
Extrator e coletor de documentos oficiais via API do Portal Nacional de
Contratações Públicas (PNCP) para DNIT, CODEVASF e outros entes federais.

OTIMIZAÇÕES v3 — CURADORIA NLP:
- Barreira 1: Filtro pré-download via metadados da API (whitelist/blacklist).
- Barreira 2: Download em pasta temporária local com deduplicação SHA-256 in-memory por id_obra.
- Barreira 3: Poda de baixa densidade (PDFs sem OCR ou < 300 chars descartados antes do commit para o Drive).
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

import pandas as pd
import requests

from src.config import logger
from src.utils import (
    arquivo_ja_existe_valido,
    filtro_pre_download_dom,
    validar_densidade_textual,
    validar_e_registrar_pdf,
    verificar_duplicata_sha256,
)


def pontuar_arquivo_pncp(item: dict[str, Any]) -> int:
    """
    Classifica a prioridade de download do arquivo PNCP baseando-se em sua tipologia.
    """
    tipo = (item.get("tipoDocumentoNome") or "").lower()
    titulo = (item.get("titulo") or item.get("nomeOriginal") or "").lower()

    score = 0
    if "edital" in tipo: score += 100
    if "termo de referência" in tipo or "termo de referencia" in tipo: score += 90
    if "estudo técnico" in tipo or "estudo tecnico" in tipo: score += 80
    if "projeto" in tipo or "memorial" in tipo: score += 75
    if "contrato" in tipo or "termo aditivo" in tipo or "termo de compromisso" in tipo: score += 85
    if "ato que autoriza" in tipo or "despacho" in tipo or "nota técnica" in tipo: score += 60

    if re.search(r"edital|termo|estudo|projeto|contrato|nota|mapa|aviso", titulo, re.I): score += 25
    if re.search(r"planilha|orçamento|cronograma|resultado", titulo, re.I): score -= 20
    return score


def coletar_obra_pncp(
    sess: requests.Session,
    cnpj: str,
    base_nome: str,
    ano: str,
    seq: str,
    row: pd.Series,
    pasta_destino: Path,
    cache_log: set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]] | None = None,
) -> list[Path]:
    """
    Consulta a API do PNCP para compras e contratos, aplicando travas de idempotência,
    filtro pré-download, download em buffer temporário local, deduplicação SHA-256,
    poda de baixa densidade e validação estrutural antes de comitar no Google Drive.
    """
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()

    # Cache de hashes para deduplicação SHA-256
    if cache_hashes is None:
        cache_hashes = {}

    # Buffer temporário local para evitar I/O desnecessário no Google Drive
    temp_dir = Path(tempfile.gettempdir()) / "tcc_pncp_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    urls_tentativas = [
        f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos",
        f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/{ano}/{seq}/arquivos",
    ]

    arquivos_validados: list[Path] = []

    for url in urls_tentativas:
        try:
            resp = sess.get(url, headers={"Accept": "application/json"}, timeout=15)
            if resp.status_code != 200:
                continue

            arquivos = resp.json()
            if not arquivos or not isinstance(arquivos, list):
                continue

            candidatos = []
            for arq in arquivos:
                score = pontuar_arquivo_pncp(arq)
                link = arq.get("url") or arq.get("uri")
                if link and score >= 0:
                    candidatos.append((score, arq))

            candidatos.sort(key=lambda x: x[0], reverse=True)
            if not candidatos:
                continue

            logger.info(f"  [{base_nome} {id_obra}] {len(candidatos)} arquivos PNCP encontrados. Processando...")

            filtrados_meta = 0
            filtrados_dedup = 0
            filtrados_poda = 0

            for idx, (score, arq) in enumerate(candidatos, start=1):
                link = arq.get("url") or arq.get("uri")
                tipo_nome = arq.get("tipoDocumentoNome") or f"DOC_{idx}"
                titulo_doc = arq.get("titulo") or arq.get("nomeOriginal") or ""
                texto_meta = f"{tipo_nome} {titulo_doc}"

                # ─── BARREIRA 1: FILTRO PRÉ-DOWNLOAD (METADADOS DA API) ─────
                deve_baixar, motivo_filtro = filtro_pre_download_dom(texto_meta)
                if not deve_baixar:
                    filtrados_meta += 1
                    logger.info(f"    [FILTRO API] Doc {idx}/{len(candidatos)}: '{texto_meta[:40]}' -> BLOQUEADO ({motivo_filtro})")
                    continue

                sufixo = re.sub(r"[^A-Za-z0-9]", "_", tipo_nome)[:30]
                nome_arquivo = f"{base_nome}_{ano}_{seq}_{idx}_{sufixo}.pdf"
                caminho_arquivo = pasta_destino / nome_arquivo

                # ─── TRAVA DE IDEMPOTÊNCIA DE DOWNLOAD ──────────────────────
                if arquivo_ja_existe_valido(caminho_arquivo):
                    logger.info(f"    [IDEMPOTÊNCIA] Arquivo já existente no Drive: {nome_arquivo} ({caminho_arquivo.stat().st_size:,} bytes). Pulando download.")
                else:
                    # Download para buffer temporário em disco local
                    temp_file = temp_dir / f"temp_{id_obra}_{idx}_{nome_arquivo}"
                    logger.info(f"    [DOWNLOAD PNCP] Baixando Doc {idx}/{len(candidatos)}: {nome_arquivo}...")
                    
                    try:
                        with sess.get(link, stream=True, timeout=45) as r_down:
                            if r_down.status_code != 200:
                                logger.warning(f"    [FALHA HTTP {r_down.status_code}] no download de {link}")
                                continue
                            with open(temp_file, "wb") as f_out:
                                for chunk in r_down.iter_content(chunk_size=8192):
                                    if chunk:
                                        f_out.write(chunk)
                    except Exception as exc_down:
                        logger.warning(f"    [ERRO REDE] Falha ao baixar {link}: {exc_down}")
                        if temp_file.exists():
                            temp_file.unlink()
                        continue

                    if not temp_file.exists() or temp_file.stat().st_size == 0:
                        continue

                    # ─── BARREIRA 2: DEDUPLICAÇÃO CRIPTOGRÁFICA SHA-256 ────────
                    eh_dup, file_hash = verificar_duplicata_sha256(temp_file, id_obra, cache_hashes)
                    if eh_dup:
                        filtrados_dedup += 1
                        logger.info(f"    [DEDUP SHA-256] Doc {idx}/{len(candidatos)}: {nome_arquivo} -> DUPLICATA (hash={file_hash[:12]}...)")
                        temp_file.unlink()
                        continue

                    # ─── BARREIRA 3: PODA DE BAIXA DENSIDADE TEXTUAL ──────────
                    aprovado, total_chars, texto_ext = validar_densidade_textual(temp_file)
                    if not aprovado:
                        filtrados_poda += 1
                        motivo_poda = "SEM_OCR" if not texto_ext else f"BAIXA_DENSIDADE({total_chars} chars)"
                        logger.info(f"    [PODA NLP] Doc {idx}/{len(candidatos)}: {nome_arquivo} -> DESCARTADO ({motivo_poda})")
                        temp_file.unlink()
                        continue

                    # Commit para o destino final (Google Drive)
                    if caminho_arquivo.exists():
                        caminho_arquivo.unlink()
                    shutil.move(str(temp_file), str(caminho_arquivo))

                # Validação e Registro de Metadados
                if arquivo_ja_existe_valido(caminho_arquivo):
                    avaliacao = validar_e_registrar_pdf(
                        caminho_pdf=caminho_arquivo,
                        base_nome=base_nome,
                        id_obra=id_obra,
                        num_inst=num_inst,
                        emp=emp,
                        obs_extra=f"Score PNCP: {score} | Tipo API: {tipo_nome}",
                        cache_log=cache_log,
                    )
                    val_data = avaliacao["validation"]
                    insp = avaliacao["inspection"]

                    if val_data["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
                        arquivos_validados.append(caminho_arquivo)
                        logger.info(f"    [+] Doc {idx}/{len(candidatos)}: {nome_arquivo} -> {val_data['result']} (Págs: {insp['pdf']['pages']}, Tipo: {val_data['document_type']})")

            # Log de resumo das filtragens
            if filtrados_meta + filtrados_dedup + filtrados_poda > 0:
                logger.info(
                    f"    [CURADORIA] {base_nome} {id_obra}: "
                    f"{filtrados_meta} bloqueados (API) | "
                    f"{filtrados_dedup} duplicatas (SHA-256) | "
                    f"{filtrados_poda} podados (densidade)"
                )

            if arquivos_validados:
                break

        except Exception as exc:
            logger.debug(f"Erro PNCP {base_nome} ({url}): {exc}")

    return arquivos_validados
