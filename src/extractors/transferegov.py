# -*- coding: utf-8 -*-
"""
src/extractors/transferegov.py
==============================
Extrator Profundo Multiformato v2 para a plataforma Transferegov / SICONV e Obrasgov (CIPI).

Melhorias da Reengenharia de Coleta (Feature 021):
1. Sessão SAML resiliente via Selenium Manager nativo (compatível com Edge 155+).
2. Varredura completa das 5 abas internas do convênio:
   - Aba `Pareceres` (`DetalharParecerProposta` -> `ParecerPropostaVisualizarParecer.do`)
   - Aba `Termos Aditivos` (`ListarTermosAditivos` -> `ListaDeTermosAditivosDoConvenioDetalhar.do`)
   - Aba `Ajustes do Plano de Trabalho` (`ListarAjustePlanoTrabalho`)
   - Aba `Processo de Execução / Licitações` (`ListarLicitacoes` -> `ListarLicitacoesDetalhar.do`)
   - Aba Inicial de Anexos (`DownloadAnexoConvenio` + `DetalharPropostaBaixar.do`)
3. Integração com Crosswalk SICONV -> Obrasgov CIPI (`api-publica.obrasgov.gestao.gov.br`).
4. Ingestão Multiformato (`.pdf`, `.docx`, `.odt`, `.rtf`) e Descompactação Cirúrgica In-Memory de `.zip`
   (`ZipFile.infolist()`), ignorando `.dwg`, `.jpg`, `.mp4`, `.xlsx` e exigindo aprovação no
   Gatekeeper Anti-Lixo (>= 800 caracteres úteis + bloqueio regex de comprovantes de e-mail).
"""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
import re
import threading
import time
from typing import Any
import zipfile

from bs4 import BeautifulSoup
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.config import ARQUIVO_LOG_COLETA, DEFAULT_HEADERS, DRIVER_PATH, ROOT_DIR, logger
from src.multiformato import (
    DocumentoProcessado,
    MIN_CHARS_UTEIS_GATEKEEPER,
    avaliar_gatekeeper_anti_lixo,
    ingerir_payload_multiformato,
    materializar_documento_aprovado_em_pdf,
)
from src.utils import (
    arquivo_ja_existe_valido,
    filtro_pre_download_dom,
    validar_e_registrar_pdf,
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


def _carregar_crosswalk_siconv_cipi() -> dict[str, list[str]]:
    """Carrega o mapeamento nr_instrumento -> lista de id_projeto_investimento (CIPI)."""
    mapa: dict[str, list[str]] = {}
    zpath = ROOT_DIR / "logs/pesquisa_siconv_dados_obrasgov_geral.zip"
    if not zpath.exists():
        return mapa
    try:
        with zipfile.ZipFile(zpath) as zf:
            raw = zf.read(zf.namelist()[0]).decode("utf-8-sig", errors="replace")
            for row in csv.DictReader(io.StringIO(raw), delimiter=";"):
                nr = (row.get("nr_instrumento") or "").strip()
                id_p = (row.get("id_projeto_investimento") or "").strip()
                if nr and id_p:
                    lista = mapa.setdefault(nr, [])
                    if id_p not in lista:
                        lista.append(id_p)
    except Exception as exc:
        logger.debug(f"Não foi possível carregar crosswalk SICONV->CIPI: {exc}")
    return mapa


def _extrair_texto_html_aba_transferegov(html_text: str, titulo_aba: str) -> str:
    """Extrai texto corrido limpo de uma página interna de Parecer / TA / Ajuste de PT do Transferegov."""
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    for menu_div in soup.find_all("div", id=re.compile(r"menu|navigation|header|footer", re.I)):
        menu_div.decompose()

    linhas: list[str] = [f"DOCUMENTO OFICIAL EXTRAÍDO DO PORTAL TRANSFEREGOV — {titulo_aba}"]
    for tr in soup.find_all("tr"):
        celulas = [
            re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()
            for td in tr.find_all(["th", "td"])
        ]
        celulas = [c for c in celulas if c and len(c) > 1]
        if celulas:
            linha = " : ".join(celulas)
            if len(linha) >= 25:
                linhas.append(linha)

    for elem in soup.find_all(["textarea", "p", "div"], class_=re.compile(r"parecer|texto|justificativa|conteudo", re.I)):
        t = re.sub(r"\s+", " ", elem.get_text(" ", strip=True)).strip()
        if len(t) >= 60:
            linhas.append(t)

    unicas: list[str] = []
    for l in linhas:
        if not unicas or unicas[-1] != l:
            unicas.append(l)
    return "\n\n".join(unicas)


class TransferegovHttpSession:
    """
    Gerenciador thread-safe de sessão autenticada Transferegov com renovação automática
    via Selenium Manager nativo (compatível com atualizações do Microsoft Edge).
    """

    def __init__(self, autenticar_imediato: bool = True) -> None:
        self.cookies: dict[str, str] = {}
        self.last_auth_time = 0.0
        self._lock = threading.Lock()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            "Referer": URL_INIT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.mapa_cipi = _carregar_crosswalk_siconv_cipi()
        if autenticar_imediato:
            self.renovar_cookies()

    def _iniciar_driver_edge(self) -> webdriver.Edge:
        options = webdriver.EdgeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        try:
            # Prioriza Selenium Manager nativo para evitar incompatibilidade de versão do msedgedriver.exe
            return webdriver.Edge(options=options)
        except Exception:
            service = Service(executable_path=str(DRIVER_PATH))
            return webdriver.Edge(service=service, options=options)

    def renovar_cookies(self) -> None:
        """Abre o Edge headless por ~3 segundos apenas para resolver SAML e obter cookies."""
        with self._lock:
            if self.cookies and (time.time() - self.last_auth_time < 300):
                return

            logger.info("  [SESSÃO TRANSFEREGOV] Autenticando via headless para captura de cookies...")
            driver = None
            try:
                driver = self._iniciar_driver_edge()
                driver.get(URL_INIT)
                wait = WebDriverWait(driver, 10)
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
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass

    def get_session(self) -> requests.Session:
        """Retorna a sessão HTTP ativa. Renova se expirada (>25 min)."""
        if time.time() - self.last_auth_time > 1500:
            self.renovar_cookies()
        return self.session


def _comitar_documento_processado(
    *,
    doc: DocumentoProcessado,
    caminho_final: Path,
    titulo_cabecalho: str,
    base_nome: str,
    id_obra: str,
    num_inst: str,
    emp: str,
    obs_extra: str,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]],
    caminho_csv: Path,
) -> Path | None:
    """
    Aplica deduplicação SHA-256 por obra, materializa o documento aprovado como PDF nativo
    e registra no `log_coleta.csv`.
    """
    if not doc.aprovado_gatekeeper:
        return None

    obra_hashes = cache_hashes.setdefault(id_obra, set())
    if doc.sha256 and doc.sha256 in obra_hashes:
        return None
    if doc.sha256:
        obra_hashes.add(doc.sha256)

    if not arquivo_ja_existe_valido(caminho_final):
        ok = materializar_documento_aprovado_em_pdf(
            doc=doc,
            caminho_destino=caminho_final,
            titulo_cabecalho=titulo_cabecalho,
        )
        if not ok or not arquivo_ja_existe_valido(caminho_final):
            return None

    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_final,
        base_nome=base_nome,
        id_obra=id_obra,
        num_inst=num_inst,
        emp=emp,
        obs_extra=f"{obs_extra} | FormatoOrig: {doc.formato_detectado} | CharsUteis: {doc.chars_uteis_corridos}",
        cache_log=cache_log,
        caminho_csv=caminho_csv,
    )
    val_data = avaliacao.get("validation", {})
    if val_data.get("result") in ("VALIDADO", "VALIDADO_COM_RESSALVAS"):
        return caminho_final
    return None


def _construir_doc_estruturado_web(
    texto_estruturado: str,
    nome_origem: str,
    formato_tag: str,
) -> DocumentoProcessado:
    """Avalia um texto estruturado extraído de aba interna (Parecer / TA / Ajuste PT) no Gatekeeper."""
    raw = texto_estruturado.encode("utf-8", errors="replace")
    sha = hashlib.sha256(raw).hexdigest()
    aprov, mot, txt_corr, chars_u, parags, eh_em, eh_ht = avaliar_gatekeeper_anti_lixo(
        texto_bruto=texto_estruturado,
        formato=formato_tag,
        tamanho_bytes=len(raw),
        min_chars_uteis=MIN_CHARS_UTEIS_GATEKEEPER,
    )
    return DocumentoProcessado(
        nome_origem=nome_origem,
        caminho_interno_zip=None,
        formato_detectado=formato_tag,
        tamanho_bytes=len(raw),
        sha256=sha,
        aprovado_gatekeeper=aprov,
        motivo_gatekeeper=mot,
        chars_brutos=len(texto_estruturado),
        chars_uteis_corridos=chars_u,
        paragrafos_validos=parags,
        eh_email_bloqueado=eh_em,
        eh_espelho_html=eh_ht,
        texto_util_preview=txt_corr[:400] if txt_corr else "",
        texto_completo_limpo=txt_corr,
        raw_bytes=raw if aprov else b"",
    )


def coletar_obra_transferegov(
    http_manager: TransferegovHttpSession,
    base_nome: str,
    row: pd.Series | dict[str, Any],
    pasta_destino: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]] | None = None,
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
    max_pareceres: int = 8,
    max_termos_aditivos: int = 8,
    max_ajustes_pt: int = 5,
    max_anexos_por_aba: int = 12,
) -> list[Path]:
    """
    Coleta dossiê documental completo de um convênio no Transferegov (Web 5 abas + Obrasgov CIPI),
    com suporte multiformato (`.pdf`, `.docx`, `.odt`, `.rtf`), descompactação cirúrgica de `.zip`
    in-memory e Gatekeeper Anti-Lixo (>= 800 caracteres úteis).
    """
    num_inst = re.sub(r"\.0+$", "", str(row.get("num. instrumento", "")).strip())
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()

    parte_convenio = num_inst.split("/")[0].strip() if "/" in num_inst else num_inst
    num_convenio = re.sub(r"\D", "", parte_convenio)
    if not num_convenio or len(num_convenio) < 5 or len(num_convenio) > 7:
        return []

    if cache_hashes is None:
        cache_hashes = {}

    # Em execução concorrente (ThreadPool), clonamos os cookies SAML para uma Session local por thread
    sess_shared = http_manager.get_session()
    sess = requests.Session()
    sess.headers.update(sess_shared.headers)
    sess.cookies.update(sess_shared.cookies)

    arquivos_validados: list[Path] = []
    filtrados_dom = filtrados_poda = zips_abertos = 0

    try:
        # ─── 0. ENRIQUECIMENTO VIA API PÚBLICA OBRASGOV (CIPI) ───────────────
        ids_cipi = http_manager.mapa_cipi.get(num_convenio, [])
        for idx_cipi, id_proj in enumerate(ids_cipi[:2], start=1):
            try:
                url_hist = (
                    "https://api-publica.obrasgov.gestao.gov.br/obras/"
                    f"historico-situacao-cancelada-paralisada?id_projeto_investimento={id_proj}&pagina=1&tamanho_da_pagina=50"
                )
                rh = sess.get(url_hist, headers=DEFAULT_HEADERS, timeout=10)
                if rh.status_code == 200:
                    itens_h = rh.json().get("data") or []
                    if itens_h:
                        blocos_h = [
                            f"HISTÓRICO OFICIAL OBRASGOV.BR (CIPI {id_proj}) — CONVÊNIO {num_convenio} — EMPREENDIMENTO: {emp}"
                        ]
                        for item in itens_h:
                            dt_h = item.get("data_historico_situacao_investimento") or ""
                            desc_h = item.get("descricao_historico_situacao_investimento") or ""
                            just_h = item.get("justificativa_cancelada_paralisada") or ""
                            blocos_h.append(f"Data: {dt_h} | Situação: {desc_h} | Justificativa Técnica: {just_h}")
                        doc_h = _construir_doc_estruturado_web(
                            "\n\n".join(blocos_h),
                            f"Obrasgov_Historico_{num_convenio}_{idx_cipi}.txt",
                            "obrasgov_api_json",
                        )
                        if doc_h.aprovado_gatekeeper:
                            caminho_h = pasta_destino / f"{base_nome}_{num_convenio}_OBRASGOV_HIST_{idx_cipi}.pdf"
                            salvo_h = _comitar_documento_processado(
                                doc=doc_h,
                                caminho_final=caminho_h,
                                titulo_cabecalho=f"HISTÓRICO OBRASGOV CIPI {id_proj} — CONVÊNIO {num_convenio}",
                                base_nome=base_nome,
                                id_obra=id_obra,
                                num_inst=num_inst,
                                emp=emp,
                                obs_extra=f"API Obrasgov CIPI {id_proj}",
                                cache_log=cache_log,
                                cache_hashes=cache_hashes,
                                caminho_csv=caminho_csv,
                            )
                            if salvo_h:
                                arquivos_validados.append(salvo_h)
            except Exception:
                pass

        # ─── 1. BUSCA DO CONVÊNIO NO PORTAL WEB TRANSFEREGOV ─────────────────
        r_busca = sess.post(URL_SEARCH, data={"numeroConvenio": num_convenio}, timeout=15)
        if r_busca.status_code != 200:
            return arquivos_validados

        soup_busca = BeautifulSoup(r_busca.text, "html.parser")
        links_conv = [
            a.get("href") for a in soup_busca.find_all("a")
            if "ResultadoDaConsultaDeConvenioSelecionarConvenio.do" in a.get("href", "")
        ]
        if not links_conv:
            return arquivos_validados

        r_detalhe = sess.get(BASE_URL + links_conv[0], timeout=15)
        if r_detalhe.status_code != 200:
            return arquivos_validados

        soup_detalhe = BeautifulSoup(r_detalhe.text, "html.parser")

        # ─── 2. ABA PARECERES TÉCNICOS E DE ENGENHARIA (PRIORIDADE 1) ────────
        url_pareceres = (
            BASE_URL
            + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarObjeto/SelecionarObjeto.do?destino=DetalharParecerProposta"
        )
        try:
            r_par = sess.get(url_pareceres, timeout=15)
            if r_par.status_code == 200:
                soup_par = BeautifulSoup(r_par.text, "html.parser")
                links_par: list[tuple[str, str]] = []
                for a in soup_par.find_all("a"):
                    href = a.get("href", "")
                    if "ParecerPropostaVisualizarParecer.do" in href or "VisualizarParecer" in href:
                        m_p = re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", href)
                        if m_p:
                            tr = a.find_parent("tr")
                            desc_par = tr.get_text(" | ", strip=True) if tr else "Parecer"
                            links_par.append((desc_par, m_p.group(1)))

                for idx_p, (desc_par, path_par) in enumerate(links_par[:max_pareceres], start=1):
                    rp_det = sess.get(BASE_URL + path_par, timeout=15)
                    if rp_det.status_code == 200:
                        texto_parecer = _extrair_texto_html_aba_transferegov(
                            rp_det.text,
                            f"PARECER TÉCNICO/ENGENHARIA #{idx_p} — CONVÊNIO {num_convenio} ({desc_par[:90]})",
                        )
                        doc_p = _construir_doc_estruturado_web(
                            texto_parecer,
                            f"Parecer_{num_convenio}_{idx_p}.txt",
                            "parecer_estruturado_web",
                        )
                        if doc_p.aprovado_gatekeeper:
                            caminho_p = pasta_destino / f"{base_nome}_{num_convenio}_PARECER_{idx_p}.pdf"
                            salvo_p = _comitar_documento_processado(
                                doc=doc_p,
                                caminho_final=caminho_p,
                                titulo_cabecalho=f"PARECER TÉCNICO TRANSFEREGOV — CONVÊNIO {num_convenio}",
                                base_nome=base_nome,
                                id_obra=id_obra,
                                num_inst=num_inst,
                                emp=emp,
                                obs_extra=f"Transferegov Aba Pareceres #{idx_p}/{len(links_par)}",
                                cache_log=cache_log,
                                cache_hashes=cache_hashes,
                                caminho_csv=caminho_csv,
                            )
                            if salvo_p:
                                arquivos_validados.append(salvo_p)
                        else:
                            filtrados_poda += 1
        except Exception as exc_par:
            logger.debug(f"Erro aba Pareceres convênio {num_convenio}: {exc_par}")

        # ─── 3. ABA TERMOS ADITIVOS DO CONVÊNIO (PRIORIDADE 2) ───────────────
        url_tas = (
            BASE_URL
            + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarTermosAditivos"
        )
        try:
            r_tas = sess.get(url_tas, timeout=15)
            if r_tas.status_code == 200:
                soup_tas = BeautifulSoup(r_tas.text, "html.parser")
                links_ta: list[tuple[str, str]] = []
                for a in soup_tas.find_all("a"):
                    href = a.get("href", "")
                    if "ListaDeTermosAditivosDoConvenioDetalhar.do" in href or "TermosAditivos" in href:
                        m_t = re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", href)
                        if m_t:
                            tr = a.find_parent("tr")
                            desc_ta = tr.get_text(" | ", strip=True) if tr else "Termo Aditivo"
                            links_ta.append((desc_ta, m_t.group(1)))

                for idx_t, (desc_ta, path_ta) in enumerate(links_ta[:max_termos_aditivos], start=1):
                    rt_det = sess.get(BASE_URL + path_ta, timeout=15)
                    if rt_det.status_code == 200:
                        texto_ta = _extrair_texto_html_aba_transferegov(
                            rt_det.text,
                            f"TERMO ADITIVO #{idx_t} — CONVÊNIO {num_convenio} ({desc_ta[:90]})",
                        )
                        doc_ta = _construir_doc_estruturado_web(
                            texto_ta,
                            f"TermoAditivo_{num_convenio}_{idx_t}.txt",
                            "termo_aditivo_estruturado_web",
                        )
                        if doc_ta.aprovado_gatekeeper:
                            caminho_ta = pasta_destino / f"{base_nome}_{num_convenio}_TERMO_ADITIVO_{idx_t}.pdf"
                            salvo_ta = _comitar_documento_processado(
                                doc=doc_ta,
                                caminho_final=caminho_ta,
                                titulo_cabecalho=f"TERMO ADITIVO TRANSFEREGOV — CONVÊNIO {num_convenio}",
                                base_nome=base_nome,
                                id_obra=id_obra,
                                num_inst=num_inst,
                                emp=emp,
                                obs_extra=f"Transferegov Aba Termos Aditivos #{idx_t}/{len(links_ta)}",
                                cache_log=cache_log,
                                cache_hashes=cache_hashes,
                                caminho_csv=caminho_csv,
                            )
                            if salvo_ta:
                                arquivos_validados.append(salvo_ta)
                        else:
                            filtrados_poda += 1
        except Exception as exc_ta:
            logger.debug(f"Erro aba Termos Aditivos convênio {num_convenio}: {exc_ta}")

        # ─── 4. ABA AJUSTES DO PLANO DE TRABALHO (PRIORIDADE 3) ──────────────
        url_apt = (
            BASE_URL
            + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarObjeto/SelecionarObjeto.do?destino=ListarAjustePlanoTrabalho"
        )
        try:
            r_apt = sess.get(url_apt, timeout=15)
            if r_apt.status_code == 200:
                soup_apt = BeautifulSoup(r_apt.text, "html.parser")
                links_apt = [
                    re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", "")).group(1)
                    for a in soup_apt.find_all("a")
                    if re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", ""))
                    and "ForwardAction" not in a.get("href", "")
                ]
                for idx_a, path_apt in enumerate(links_apt[:max_ajustes_pt], start=1):
                    ra_det = sess.get(BASE_URL + path_apt, timeout=15)
                    if ra_det.status_code == 200:
                        texto_apt = _extrair_texto_html_aba_transferegov(
                            ra_det.text,
                            f"AJUSTE DO PLANO DE TRABALHO #{idx_a} — CONVÊNIO {num_convenio}",
                        )
                        doc_apt = _construir_doc_estruturado_web(
                            texto_apt,
                            f"AjustePT_{num_convenio}_{idx_a}.txt",
                            "ajuste_pt_estruturado_web",
                        )
                        if doc_apt.aprovado_gatekeeper:
                            caminho_apt = pasta_destino / f"{base_nome}_{num_convenio}_AJUSTE_PT_{idx_a}.pdf"
                            salvo_apt = _comitar_documento_processado(
                                doc=doc_apt,
                                caminho_final=caminho_apt,
                                titulo_cabecalho=f"AJUSTE DO PLANO DE TRABALHO — CONVÊNIO {num_convenio}",
                                base_nome=base_nome,
                                id_obra=id_obra,
                                num_inst=num_inst,
                                emp=emp,
                                obs_extra=f"Transferegov Aba Ajustes PT #{idx_a}/{len(links_apt)}",
                                cache_log=cache_log,
                                cache_hashes=cache_hashes,
                                caminho_csv=caminho_csv,
                            )
                            if salvo_apt:
                                arquivos_validados.append(salvo_apt)
                        else:
                            filtrados_poda += 1
        except Exception as exc_apt:
            logger.debug(f"Erro aba Ajustes PT convênio {num_convenio}: {exc_apt}")

        # ─── 5. ABA PROCESSO DE EXECUÇÃO / LICITAÇÕES (PRIORIDADE 4) ─────────
        url_lic = (
            BASE_URL
            + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarLicitacoes"
        )
        try:
            r_lic = sess.get(url_lic, timeout=15)
            if r_lic.status_code == 200:
                soup_lic = BeautifulSoup(r_lic.text, "html.parser")
                links_lic = [
                    re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", "")).group(1)
                    for a in soup_lic.find_all("a")
                    if "ListarLicitacoesDetalhar.do" in a.get("href", "")
                    and re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", ""))
                ]
                for idx_l, path_lic in enumerate(links_lic[:4], start=1):
                    rl_det = sess.get(BASE_URL + path_lic, timeout=15)
                    if rl_det.status_code == 200:
                        soup_ld = BeautifulSoup(rl_det.text, "html.parser")
                        dl_lic = [
                            (
                                (a.find_parent("tr").get_text(" ", strip=True) if a.find_parent("tr") else a.get_text(strip=True)),
                                re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", "")).group(1),
                            )
                            for a in soup_ld.find_all("a")
                            if ("Download" in a.get("href", "") or "Baixar" in a.get("href", ""))
                            and re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", ""))
                        ]
                        for idx_f, (nome_linha, path_f) in enumerate(dl_lic[:6], start=1):
                            deve_baixar, _ = filtro_pre_download_dom(nome_linha)
                            if not deve_baixar:
                                filtrados_dom += 1
                                continue
                            rf = sess.get(BASE_URL + path_f, timeout=25)
                            if rf.status_code == 200 and rf.content:
                                cd = rf.headers.get("Content-Disposition", "")
                                m_fn = re.search(r'filename="?([^";]+)"?', cd)
                                nome_f = m_fn.group(1).strip() if m_fn else f"Execucao_{idx_l}_{idx_f}.bin"
                                docs_p, insp_z = ingerir_payload_multiformato(rf.content, nome_f)
                                if insp_z:
                                    zips_abertos += 1
                                for sub_i, doc_item in enumerate(docs_p, start=1):
                                    if not doc_item.aprovado_gatekeeper:
                                        filtrados_poda += 1
                                        continue
                                    suf = re.sub(r"[^A-Za-z0-9]", "_", Path(doc_item.nome_origem).stem)[:30]
                                    caminho_f = pasta_destino / f"{base_nome}_{num_convenio}_EXEC_{idx_l}_{idx_f}_{sub_i}_{suf}.pdf"
                                    salvo_f = _comitar_documento_processado(
                                        doc=doc_item,
                                        caminho_final=caminho_f,
                                        titulo_cabecalho=f"EXECUÇÃO/LICITAÇÃO TRANSFEREGOV — CONVÊNIO {num_convenio}",
                                        base_nome=base_nome,
                                        id_obra=id_obra,
                                        num_inst=num_inst,
                                        emp=emp,
                                        obs_extra=f"Transferegov Aba Execução #{idx_l}.{idx_f}",
                                        cache_log=cache_log,
                                        cache_hashes=cache_hashes,
                                        caminho_csv=caminho_csv,
                                    )
                                    if salvo_f:
                                        arquivos_validados.append(salvo_f)
        except Exception as exc_lic:
            logger.debug(f"Erro aba Licitações convênio {num_convenio}: {exc_lic}")

        # ─── 6. ABA INICIAL DE ANEXOS DO CONVÊNIO E PROPOSTA (COM .ZIP IN-MEMORY) ─
        anexos_elems = [
            a for a in soup_detalhe.find_all("a")
            if any(tok in a.get("href", "") for tok in ("DownloadAnexoConvenio", "DetalharPropostaBaixar"))
        ]
        total_anexos = len(anexos_elems)

        for idx, anexo_a in enumerate(anexos_elems[:max_anexos_por_aba], start=1):
            tr = anexo_a.find_parent("tr")
            nome_tabela = tr.get_text(separator=" ", strip=True) if tr else anexo_a.get_text(strip=True)

            # Barreira 1: Filtro Pré-Download DOM v2 (permite .zip/.docx/.odt/.rtf/.pdf e prioriza whitelist técnica)
            deve_baixar, _ = filtro_pre_download_dom(nome_tabela)
            if not deve_baixar:
                filtrados_dom += 1
                continue

            href = anexo_a.get("href", "")
            m = re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", href)
            path_download = m.group(1) if m else href
            if not path_download.startswith("/"):
                continue

            try:
                r_down = sess.get(BASE_URL + path_download, timeout=30)
                if r_down.status_code != 200 or not r_down.content:
                    continue

                cd = r_down.headers.get("Content-Disposition", "")
                m_fn = re.search(r'filename="?([^";]+)"?', cd)
                nome_real = m_fn.group(1).strip() if m_fn else f"Anexo_{idx}_{nome_tabela[:30]}.bin"

                docs_proc, insp_zip = ingerir_payload_multiformato(r_down.content, nome_real)
                if insp_zip:
                    zips_abertos += 1

                for sub_idx, doc_item in enumerate(docs_proc, start=1):
                    if not doc_item.aprovado_gatekeeper:
                        filtrados_poda += 1
                        continue
                    nome_sufixo = re.sub(r"[^A-Za-z0-9]", "_", Path(doc_item.nome_origem).stem)[:32]
                    nome_padrao = (
                        f"{base_nome}_{num_convenio}_{idx}_{sub_idx}_{nome_sufixo}.pdf"
                        if len(docs_proc) > 1
                        else f"{base_nome}_{num_convenio}_{idx}_{nome_sufixo}.pdf"
                    )
                    caminho_final = pasta_destino / nome_padrao
                    salvo = _comitar_documento_processado(
                        doc=doc_item,
                        caminho_final=caminho_final,
                        titulo_cabecalho=f"ANEXO OFICIAL TRANSFEREGOV — CONVÊNIO {num_convenio} ({doc_item.nome_origem})",
                        base_nome=base_nome,
                        id_obra=id_obra,
                        num_inst=num_inst,
                        emp=emp,
                        obs_extra=f"Transferegov Anexo {idx}/{total_anexos} ({doc_item.nome_origem})",
                        cache_log=cache_log,
                        cache_hashes=cache_hashes,
                        caminho_csv=caminho_csv,
                    )
                    if salvo:
                        arquivos_validados.append(salvo)
            except Exception:
                continue

        if filtrados_dom + filtrados_poda + zips_abertos > 0:
            logger.info(
                f"    [CURADORIA TRANSFEREGOV] {base_nome} {id_obra} (Conv {num_convenio}): "
                f"+{len(arquivos_validados)} aprovados | {zips_abertos} ZIPs abertos in-memory | "
                f"{filtrados_dom} DOM bloqueados | {filtrados_poda} Gatekeeper podados"
            )

        return arquivos_validados

    except Exception as exc:
        logger.debug(f"Erro Transferegov HTTP convênio {num_convenio}: {exc}")
        return arquivos_validados
