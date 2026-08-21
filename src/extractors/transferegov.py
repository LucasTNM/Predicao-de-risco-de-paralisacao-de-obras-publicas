# -*- coding: utf-8 -*-
"""
src/extractors/transferegov.py
==============================
Extrator de altíssimo throughput para a plataforma Transferegov / SICONV.
Utiliza Selenium estritamente para obter os cookies de sessão (SAML) e realiza 
a navegação/download via requisições HTTP puras (requests) com pool de conexões.

OTIMIZAÇÕES DE MLOps:
- Idempotência de Disco (Google Drive)
- Barreira 1: Filtro pré-download DOM (whitelist/blacklist)
- Barreira 2: Deduplicação SHA-256 in-memory
- Barreira 3: Poda de baixa densidade textual
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import tempfile
import threading
import time

from bs4 import BeautifulSoup
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.config import DRIVER_PATH, logger
from src.utils import (
    arquivo_ja_existe_valido,
    filtro_pre_download_dom,
    validar_densidade_textual,
    validar_e_registrar_pdf,
    verificar_duplicata_sha256,
)

URL_INIT = (
    "https://discricionarias.transferegov.sistema.gov.br/voluntarias/"
    "ForwardAction.do?modulo=Principal&path=/MostraPrincipalConsultarConvenio.do"
    "&Usr=guest&Pwd=guest"
)
URL_SEARCH = (
    "https://discricionarias.transferegov.sistema.gov.br/voluntarias/"
    "ConsultarProposta/PreenchaOsDadosDaConsultaConsultar.do?tipo_consulta=CONSULTA_RAPIDA"
)
BASE_URL = "https://discricionarias.transferegov.sistema.gov.br"


class TransferegovHttpSession:
    """
    Gerenciador thread-safe de sessão autenticada Transferegov com renovação automática.
    """

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}
        self.last_auth_time = 0.0
        self._lock = threading.Lock()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Referer": URL_INIT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.renovar_cookies()

    def renovar_cookies(self) -> None:
        """Abre o Edge headless por ~3 segundos apenas para resolver SAML e obter cookies."""
        with self._lock:
            if self.cookies and (time.time() - self.last_auth_time < 300):
                return

            logger.info("  [SESSÃO TRANSFEREGOV] Autenticando via headless para captura de cookies...")
            options = webdriver.EdgeOptions()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            service = Service(executable_path=str(DRIVER_PATH))
            driver = webdriver.Edge(service=service, options=options)

            try:
                driver.get(URL_INIT)
                wait = WebDriverWait(driver, 8)
                wait.until(EC.presence_of_element_located((By.ID, "consultarNumeroConvenio")))

                selenium_cookies = driver.get_cookies()
                self.cookies = {c["name"]: c["value"] for c in selenium_cookies}

                self.session.cookies.clear()
                for name, val in self.cookies.items():
                    self.session.cookies.set(name, val)

                self.last_auth_time = time.time()
                logger.info(f"  [SESSÃO TRANSFEREGOV] Sucesso! {len(self.cookies)} cookies injetados na sessão HTTP.")
            except Exception as exc:
                logger.error(f"  [FALHA AUTH TRANSFEREGOV] Não foi possível obter cookies: {exc}")
            finally:
                driver.quit()

    def get_session(self) -> requests.Session:
        """Retorna a sessão HTTP ativa. Renova se expirada (>25 min)."""
        if time.time() - self.last_auth_time > 1500:
            self.renovar_cookies()
        return self.session


def coletar_obra_transferegov(
    http_manager: TransferegovHttpSession,
    base_nome: str,
    row: pd.Series,
    pasta_destino: Path,
    cache_log: set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]] | None = None,
) -> list[Path]:
    """
    Coleta documentos de um convênio usando HTTP puro com validações rigorosas de MLOps.
    """
    num_inst = str(row.get("num. instrumento", "")).strip()
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()

    num_convenio = re.sub(r"\D", "", num_inst)
    if not num_convenio or len(num_convenio) < 5 or len(num_convenio) > 7:
        return []

    if cache_hashes is None:
        cache_hashes = {}

    sess = http_manager.get_session()
    temp_dir = Path(tempfile.gettempdir()) / "tcc_transferegov_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    arquivos_validados: list[Path] = []
    filtrados_dom = filtrados_dedup = filtrados_poda = 0

    try:
        # 1. Consulta POST via HTTP
        r_busca = sess.post(URL_SEARCH, data={"numeroConvenio": num_convenio}, timeout=12)
        if r_busca.status_code != 200:
            return []

        soup_busca = BeautifulSoup(r_busca.text, "html.parser")
        links_conv = [
            a.get("href") for a in soup_busca.find_all("a")
            if "ResultadoDaConsultaDeConvenioSelecionarConvenio.do" in a.get("href", "")
        ]

        if not links_conv:
            return []

        # 2. Navega para a página de anexos
        url_detalhe = BASE_URL + links_conv[0]
        r_detalhe = sess.get(url_detalhe, timeout=12)
        if r_detalhe.status_code != 200:
            return []

        soup_detalhe = BeautifulSoup(r_detalhe.text, "html.parser")
        anexos_elems = [
            a for a in soup_detalhe.find_all("a")
            if "DownloadAnexoConvenio" in a.get("href", "")
        ]

        if not anexos_elems:
            return []

        total_anexos = len(anexos_elems)

        # 3. Processamento iterativo dos anexos
        for idx, anexo_a in enumerate(anexos_elems, start=1):
            tr = anexo_a.find_parent("tr")
            nome_tabela = tr.get_text(separator=" ", strip=True) if tr else anexo_a.get_text(strip=True)

            if any(ext in nome_tabela.lower() for ext in [".zip", ".xlsx", ".rar", ".dwg", ".csv"]):
                continue

            # --- BARREIRA 1: FILTRO DOM ---
            deve_baixar, motivo_filtro = filtro_pre_download_dom(nome_tabela)
            if not deve_baixar:
                filtrados_dom += 1
                continue

            nome_sufixo = re.sub(r"[^A-Za-z0-9]", "_", nome_tabela)[:35]
            nome_padrao = f"{base_nome}_{num_convenio}_{idx}_{nome_sufixo}.pdf"
            caminho_final = pasta_destino / nome_padrao

            # --- TRAVA IDEMPOTÊNCIA DISCO ---
            if arquivo_ja_existe_valido(caminho_final):
                continue

            href = anexo_a.get("href", "")
            m = re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", href)
            path_download = m.group(1) if m else href
            url_download = BASE_URL + path_download

            temp_file = temp_dir / f"temp_{id_obra}_{idx}_{nome_padrao}"

            # Download em Chunks (Evita carregar PDFs de 100MB na memória)
            try:
                with sess.get(url_download, stream=True, timeout=30) as r_down:
                    if r_down.status_code != 200:
                        continue
                    with open(temp_file, "wb") as f_out:
                        for chunk in r_down.iter_content(chunk_size=8192):
                            if chunk:
                                f_out.write(chunk)
            except Exception:
                if temp_file.exists():
                    temp_file.unlink()
                continue

            if not temp_file.exists() or temp_file.stat().st_size == 0:
                continue

            # --- BARREIRA 2: DEDUP SHA-256 ---
            eh_dup, file_hash = verificar_duplicata_sha256(temp_file, id_obra, cache_hashes)
            if eh_dup:
                filtrados_dedup += 1
                temp_file.unlink()
                continue

            # --- BARREIRA 3: DENSIDADE NLP ---
            aprovado, total_chars, texto_ext = validar_densidade_textual(temp_file)
            if not aprovado:
                filtrados_poda += 1
                temp_file.unlink()
                continue

            # Commit Seguro
            if caminho_final.exists():
                caminho_final.unlink()
            shutil.move(str(temp_file), str(caminho_final))

            # Validação Final e Inserção no Log
            if arquivo_ja_existe_valido(caminho_final):
                avaliacao = validar_e_registrar_pdf(
                    caminho_pdf=caminho_final,
                    base_nome=base_nome,
                    id_obra=id_obra,
                    num_inst=num_inst,
                    emp=emp,
                    obs_extra=f"Transferegov HTTP Anexo {idx}/{total_anexos}",
                    cache_log=cache_log,
                )
                val_data = avaliacao["validation"]
                if val_data["result"] in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
                    arquivos_validados.append(caminho_final)

        if filtrados_dom + filtrados_dedup + filtrados_poda > 0:
            logger.info(
                f"    [CURADORIA] {base_nome} {id_obra}: "
                f"{filtrados_dom} DOM | {filtrados_dedup} SHA-256 | {filtrados_poda} NLP Poda"
            )

        return arquivos_validados

    except Exception as exc:
        logger.debug(f"Erro Transferegov HTTP convênio {num_convenio}: {exc}")
        return []
