# -*- coding: utf-8 -*-
"""
revisao_coleta/sondagem_endpoints.py
====================================
FASE 3: Conectores de Sondagem Profunda de Novos Endpoints e Formatos.

Investiga:
1. Transferegov (Web Abas Internas + API de Dados Abertos + Obrasgov CIPI):
   - Abas Web SICONV/Transferegov:
     * Aba Inicial de Anexos do Convênio (`DetalharPropostaDownloadAnexoConvenio.do` + `DetalharPropostaBaixar.do` + `DetalharPropostaBaixarContrapartida.do`)
     * Aba `Pareceres` (`DetalharParecerProposta` -> `ParecerPropostaVisualizarParecer.do` -> pareceres técnicos e de engenharia completos!)
     * Aba `TAs` / Termos Aditivos (`ListarTermosAditivos` -> `ListaDeTermosAditivosDoConvenioDetalhar.do` -> justificativas e anexos de aditivos)
     * Aba `Ajustes do PT` (`ListarAjustePlanoTrabalho` -> solicitações e pareceres de ajuste do Plano de Trabalho)
     * Aba `Processo de Execução` / Licitações (`ListarLicitacoes` -> `ListarLicitacoesDetalhar.do` -> editais, contratos e anexos de execução)
     * Aba `Relatórios de Execução` (`ListarRelatoriosExecucao` -> `ListaDeRelatoriosVisualizar.do`)
     * Microsserviços modernos: `medicao.transferegov.sistema.gov.br` (Acompanhamento de Obras / Laudos de Vistoria) e `instrumentoscontratuais.transferegov.sistema.gov.br`
   - API de Dados Abertos do Transferegov (`api.transferegov.gestao.gov.br`) e Dumps/Crosswalk Obrasgov (`api-publica.obrasgov.gestao.gov.br/obras/historico-situacao-cancelada-paralisada`).
2. PNCP (Contratos, Termos Aditivos, Termos de Rescisão e Compras Vinculadas):
   - Endpoint de consulta de Contratos (`/api/consulta/v1/contratos?cnpjOrgao=04892707000100`);
   - Endpoint de arquivos do Contrato (`/api/pncp/v1/orgaos/{cnpj}/contratos/{ano}/{seq}/arquivos`);
   - Endpoint de Termos de Contrato / Aditivos / Rescisões (`/api/pncp/v1/orgaos/{cnpj}/contratos/{ano}/{seq}/termos` e `/termos/{seqTermo}/arquivos`);
   - Endpoint de Compra vinculada (`numeroControlePncpCompra` -> `/api/pncp/v1/orgaos/{cnpj}/compras/{anoCompra}/{seqCompra}/arquivos`), com descompactação in-memory de `.zip` e leitura de `.docx`/`.odt`/`.rtf`/`.pdf`.
3. SIMEC (Obras 2.0) e SISMOB (Ministério da Saúde):
   - Sondagem do portal público SIMEC Obras 2.0 (`simec.mec.gov.br/painelObras` / `simec.mec.gov.br/obras2` - abas de Restrições e Inconformidades, Vistorias/Supervisão e Documentos Anexos) e verificação de barreiras de reCAPTCHA/autenticação;
   - Sondagem da API pública SISMOB Cidadão (`sismobcidadao.saude.gov.br/api/public/obras`) para recuperar `propostaId`, histórico de situação, `dsJustificativa`, dados de execução, empresas e vistorias.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
from typing import Any
import zipfile

from bs4 import BeautifulSoup
import requests
from selenium import webdriver

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from revisao_coleta.motor_multiformato import (
    DocumentoProcessado,
    MIN_CHARS_UTEIS_GATEKEEPER,
    avaliar_gatekeeper_anti_lixo,
    filtro_pre_download_dom_v2,
    ingerir_payload_multiformato,
    processar_bytes_documento,
)
from src.config import CNPJ_DNIT, DEFAULT_HEADERS
from src.extractors.transferegov import BASE_URL, URL_INIT, URL_SEARCH
from src.utils import filtro_pre_download_dom


def _normalizar_ascii(texto: str) -> str:
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("ASCII").lower().strip()


# ─────────────────────────────────────────────────────────────────────────────
# 1. GERENCIADOR DE SESSÃO TRANSFEREGOV (COMPATÍVEL COM SELENIUM MANAGER / EDGE 155+)
# ─────────────────────────────────────────────────────────────────────────────

class TransferegovProbeSession:
    """Obtém cookies SAML do Transferegov usando Selenium Manager nativo (compatível com Edge 155+)."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Referer": URL_INIT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.autenticado = False
        self.erro_auth: str | None = None
        self._autenticar()

    def _autenticar(self) -> None:
        options = webdriver.EdgeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        driver = None
        try:
            # Usa Selenium Manager automático (sem forçar msedgedriver.exe legado v151)
            driver = webdriver.Edge(options=options)
            driver.get(URL_INIT)
            time.sleep(4.0)
            cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
            for k, v in cookies.items():
                self.session.cookies.set(k, v)
            self.autenticado = "JSESSIONID" in cookies
        except Exception as exc:
            self.erro_auth = str(exc)
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass


# ─────────────────────────────────────────────────────────────────────────────
# 2. CARREGAMENTO DO CROSSWALK SICONV -> OBRASGOV (CIPI)
# ─────────────────────────────────────────────────────────────────────────────

def carregar_crosswalk_siconv_cipi() -> dict[str, list[dict[str, str]]]:
    """Lê o arquivo `logs/pesquisa_siconv_dados_obrasgov_geral.zip` e mapeia nr_instrumento -> registros CIPI."""
    mapa: dict[str, list[dict[str, str]]] = {}
    zpath = ROOT_DIR / "logs/pesquisa_siconv_dados_obrasgov_geral.zip"
    if not zpath.exists():
        return mapa
    try:
        with zipfile.ZipFile(zpath) as zf:
            raw = zf.read(zf.namelist()[0]).decode("utf-8-sig", errors="replace")
            for row in csv.DictReader(io.StringIO(raw), delimiter=";"):
                nr = (row.get("nr_instrumento") or "").strip()
                if nr:
                    mapa.setdefault(nr, []).append(row)
    except Exception:
        pass
    return mapa


def carregar_contratos_siconv_cipi() -> dict[str, list[dict[str, str]]]:
    """Lê `logs/pesquisa_siconv_contrato_cipi.zip` e mapeia ID_PROJETO_INVESTIMENTO -> contratos."""
    mapa: dict[str, list[dict[str, str]]] = {}
    zpath = ROOT_DIR / "logs/pesquisa_siconv_contrato_cipi.zip"
    if not zpath.exists():
        return mapa
    try:
        with zipfile.ZipFile(zpath) as zf:
            raw = zf.read(zf.namelist()[0]).decode("utf-8-sig", errors="replace")
            for row in csv.DictReader(io.StringIO(raw), delimiter=";"):
                id_proj = (row.get("ID_PROJETO_INVESTIMENTO") or "").strip()
                if id_proj:
                    mapa.setdefault(id_proj, []).append(row)
    except Exception:
        pass
    return mapa


# ─────────────────────────────────────────────────────────────────────────────
# 3. SONDAGEM PROFUNDA TRANSFEREGOV (WEB ABAS INTERNAS + API DADOS ABERTOS + CIPI)
# ─────────────────────────────────────────────────────────────────────────────

def _extrair_texto_html_estruturado(html_text: str, titulo_aba: str) -> str:
    """Extrai texto limpo das tabelas e campos de uma página interna de Parecer / TA / Ajuste PT / Relatório do Transferegov."""
    soup = BeautifulSoup(html_text, "html.parser")
    # Remove scripts, styles e menus de navegação lateral/topo
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    for menu_div in soup.find_all("div", id=re.compile(r"menu| navigation|header|footer", re.I)):
        menu_div.decompose()

    linhas: list[str] = [f"DOCUMENTO OFICIAL EXTRAÍDO DO PORTAL TRANSFEREGOV — ABA: {titulo_aba}"]
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

    # Também captura divs/textareas de pareceres técnicos longos
    for elem in soup.find_all(["textarea", "p", "div"], class_=re.compile(r"parecer|texto|justificativa|conteudo", re.I)):
        t = re.sub(r"\s+", " ", elem.get_text(" ", strip=True)).strip()
        if len(t) >= 60:
            linhas.append(t)

    # Deduplica linhas consecutivas iguais
    unicas: list[str] = []
    for l in linhas:
        if not unicas or unicas[-1] != l:
            unicas.append(l)
    return "\n\n".join(unicas)


def sondar_obra_transferegov_profundo(
    obra: dict[str, Any],
    sess: requests.Session,
    mapa_cipi: dict[str, list[dict[str, str]]],
    mapa_contratos_cipi: dict[str, list[dict[str, str]]],
    max_downloads_por_aba: int = 8,
) -> dict[str, Any]:
    """
    Sonda profundamente uma obra CAIXA/FUNASA no Transferegov (Web + API Dados Abertos + Obrasgov CIPI).
    Compara o que o extrator da Sprint 1 pegava vs. o que o novo extrator multiformato + novas abas descobre.
    """
    num_inst = str(obra.get("num_instrumento", "")).strip()
    num_convenio = re.sub(r"\D", "", num_inst)

    resultado: dict[str, Any] = {
        "id_obra": obra["id"],
        "base": obra["base_de_dados"],
        "num_instrumento": num_inst,
        "num_convenio_limpo": num_convenio,
        "convenio_encontrado_web": False,
        "id_proposta_interno": None,
        "sprint1_simulacao": {
            "anexos_aba_inicial_DownloadAnexoConvenio": 0,
            "bloqueados_extensao_zip_xlsx": 0,
            "bloqueados_filtro_dom_v1": 0,
            "aprovados_sprint1": 0,
        },
        "novos_endpoints_web": {
            "aba_inicial_todos_links_download": 0,
            "aba_pareceres_count": 0,
            "aba_termos_aditivos_count": 0,
            "aba_ajustes_pt_count": 0,
            "aba_licitacoes_execucao_count": 0,
            "aba_relatorios_execucao_count": 0,
            "aba_acompanhamento_obras_medicao_status": None,
        },
        "api_dados_abertos_e_obrasgov": {
            "api_transferegov_especial_status": None,
            "crosswalk_cipi_encontrado": False,
            "id_projeto_investimento_cipi": [],
            "contratos_cipi_count": 0,
            "historico_paralisacao_obrasgov_count": 0,
            "justificativas_obrasgov": [],
        },
        "documentos_aprovados_gatekeeper": [],
        "documentos_rejeitados_gatekeeper": [],
        "zips_inspecionados": [],
    }

    # 1. Sonda Crosswalk SICONV -> CIPI e API Obrasgov (`api-publica.obrasgov.gestao.gov.br`)
    if num_convenio and num_convenio in mapa_cipi:
        registros_cipi = mapa_cipi[num_convenio]
        resultado["api_dados_abertos_e_obrasgov"]["crosswalk_cipi_encontrado"] = True
        ids_proj = list({r.get("id_projeto_investimento", "").strip() for r in registros_cipi if r.get("id_projeto_investimento")})
        resultado["api_dados_abertos_e_obrasgov"]["id_projeto_investimento_cipi"] = ids_proj

        for id_p in ids_proj[:3]:
            contratos_c = mapa_contratos_cipi.get(id_p, [])
            resultado["api_dados_abertos_e_obrasgov"]["contratos_cipi_count"] += len(contratos_c)
            try:
                url_hist = f"https://api-publica.obrasgov.gestao.gov.br/obras/historico-situacao-cancelada-paralisada?id_projeto_investimento={id_p}&pagina=1&tamanho_da_pagina=20"
                rh = requests.get(url_hist, headers=DEFAULT_HEADERS, timeout=10)
                if rh.status_code == 200:
                    dh = rh.json().get("data") or []
                    resultado["api_dados_abertos_e_obrasgov"]["historico_paralisacao_obrasgov_count"] += len(dh)
                    for item_h in dh:
                        just = item_h.get("justificativa_cancelada_paralisada") or item_h.get("descricao_historico_situacao_investimento")
                        if just:
                            resultado["api_dados_abertos_e_obrasgov"]["justificativas_obrasgov"].append(str(just))
            except Exception:
                pass

    # 2. Sonda API de Dados Abertos do Transferegov (`api.transferegov.gestao.gov.br`)
    try:
        r_api_tg = requests.get(
            f"https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao? limit=1",
            headers=DEFAULT_HEADERS,
            timeout=8,
        )
        resultado["api_dados_abertos_e_obrasgov"]["api_transferegov_especial_status"] = r_api_tg.status_code
    except Exception as exc:
        resultado["api_dados_abertos_e_obrasgov"]["api_transferegov_especial_status"] = f"ERR:{type(exc).__name__}"

    # Se não tiver número de convênio de 5 a 7 dígitos (ex.: TC/PAC da FUNASA), retorna o diagnóstico de identidade
    if not num_convenio or len(num_convenio) < 5 or len(num_convenio) > 7:
        return resultado

    # 3. Busca Web no Portal Transferegov Discricionárias/Voluntárias
    try:
        r_busca = sess.post(URL_SEARCH, data={"numeroConvenio": num_convenio}, timeout=12)
        if r_busca.status_code != 200:
            return resultado

        soup_busca = BeautifulSoup(r_busca.text, "html.parser")
        links_conv = [
            a.get("href") for a in soup_busca.find_all("a")
            if "ResultadoDaConsultaDeConvenioSelecionarConvenio.do" in a.get("href", "")
        ]
        if not links_conv:
            return resultado

        resultado["convenio_encontrado_web"] = True
        r_detalhe = sess.get(BASE_URL + links_conv[0], timeout=12)
        if r_detalhe.status_code != 200:
            return resultado

        soup_detalhe = BeautifulSoup(r_detalhe.text, "html.parser")

        # Extrair idProposta dos links de microsserviços (Acompanhamento de Obras / VRPL / Instrumentos Contratuais)
        m_prop = re.search(r"idProposta=(\d+)|/proposta/(\d+)", r_detalhe.text)
        if m_prop:
            resultado["id_proposta_interno"] = m_prop.group(1) or m_prop.group(2)

        # 3.1 Avaliar Aba Inicial de Anexos (Sprint 1 vs. Novo Motor)
        # Na Sprint 1, procurava apenas `"DownloadAnexoConvenio" in a.get("href", "")`.
        # Mas na página existem também `DetalharPropostaBaixar.do` e `DetalharPropostaBaixarContrapartida.do`!
        links_download_inicial = []
        for a in soup_detalhe.find_all("a"):
            href = a.get("href", "")
            if any(tok in href for tok in ("DownloadAnexoConvenio", "DetalharPropostaBaixar")):
                tr = a.find_parent("tr")
                nome_tabela = tr.get_text(" ", strip=True) if tr else a.get_text(strip=True)
                links_download_inicial.append((nome_tabela, href, "DownloadAnexoConvenio" in href))

        resultado["novos_endpoints_web"]["aba_inicial_todos_links_download"] = len(links_download_inicial)
        resultado["sprint1_simulacao"]["anexos_aba_inicial_DownloadAnexoConvenio"] = sum(
            1 for _, _, eh_s1 in links_download_inicial if eh_s1
        )

        # Processa downloads da aba inicial (até max_downloads_por_aba)
        for idx_dl, (nome_tabela, href, eh_s1) in enumerate(links_download_inicial[:max_downloads_por_aba], start=1):
            if eh_s1:
                if any(ext in nome_tabela.lower() for ext in [".zip", ".xlsx", ".rar", ".dwg", ".csv"]):
                    resultado["sprint1_simulacao"]["bloqueados_extensao_zip_xlsx"] += 1
                else:
                    ok_s1, _ = filtro_pre_download_dom(nome_tabela)
                    if not ok_s1:
                        resultado["sprint1_simulacao"]["bloqueados_filtro_dom_v1"] += 1

            ok_v2, mot_v2 = filtro_pre_download_dom_v2(nome_tabela)
            if not ok_v2:
                continue

            m_url = re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", href)
            path_dl = m_url.group(1) if m_url else href
            if not path_dl.startswith("/"):
                continue

            try:
                r_dl = sess.get(BASE_URL + path_dl, timeout=20)
                if r_dl.status_code == 200 and r_dl.content:
                    cd = r_dl.headers.get("Content-Disposition", "")
                    m_fn = re.search(r'filename="?([^";]+)"?', cd)
                    nome_real = m_fn.group(1).strip() if m_fn else f"Anexo_{idx_dl}_{nome_tabela[:30]}.bin"
                    docs_proc, insp_zip = ingerir_payload_multiformato(r_dl.content, nome_real)
                    if insp_zip:
                        resultado["zips_inspecionados"].append({
                            "aba": "ABA_INICIAL_ANEXOS",
                            "nome_zip": insp_zip.nome_zip,
                            "total_entradas": insp_zip.total_entradas_zip,
                            "ignorados": len(insp_zip.entradas_ignoradas_engenharia_midia),
                            "extraidos": len(insp_zip.entradas_texto_rico_extraidas),
                        })
                    for d in docs_proc:
                        info_d = d.to_summary_dict()
                        info_d["endpoint_origem"] = "TRANSFEREGOV_ABA_INICIAL"
                        info_d["linha_tabela"] = nome_tabela[:120]
                        if d.aprovado_gatekeeper:
                            resultado["documentos_aprovados_gatekeeper"].append(info_d)
                            if eh_s1 and d.formato_detectado == "pdf" and filtro_pre_download_dom(nome_tabela)[0]:
                                resultado["sprint1_simulacao"]["aprovados_sprint1"] += 1
                        else:
                            resultado["documentos_rejeitados_gatekeeper"].append(info_d)
            except Exception:
                pass

        # 3.2 Sonda Aba `Pareceres` (Pareceres Técnicos, Jurídicos e de Engenharia da Proposta/Plano de Trabalho)
        url_pareceres = BASE_URL + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarObjeto/SelecionarObjeto.do?destino=DetalharParecerProposta"
        r_par = sess.get(url_pareceres, timeout=12)
        if r_par.status_code == 200:
            soup_par = BeautifulSoup(r_par.text, "html.parser")
            links_par = []
            for a in soup_par.find_all("a"):
                href = a.get("href", "")
                if "ParecerPropostaVisualizarParecer.do" in href or "VisualizarParecer" in href:
                    m_p = re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", href)
                    if m_p:
                        tr = a.find_parent("tr")
                        desc_par = tr.get_text(" | ", strip=True) if tr else "Parecer"
                        links_par.append((desc_par, m_p.group(1)))

            resultado["novos_endpoints_web"]["aba_pareceres_count"] = len(links_par)
            for idx_p, (desc_par, path_par) in enumerate(links_par[:5], start=1):
                try:
                    rp_det = sess.get(BASE_URL + path_par, timeout=12)
                    if rp_det.status_code == 200:
                        texto_parecer = _extrair_texto_html_estruturado(rp_det.text, f"PARECER TÉCNICO #{idx_p} ({desc_par[:80]})")
                        aprov, mot, txt_corr, chars_u, parags, eh_em, eh_ht = avaliar_gatekeeper_anti_lixo(
                            texto_bruto=texto_parecer,
                            formato="parecer_estruturado_web",
                            tamanho_bytes=len(rp_det.content),
                        )
                        doc_info = {
                            "nome_origem": f"Parecer_Transferegov_{num_convenio}_{idx_p}.txt",
                            "endpoint_origem": "TRANSFEREGOV_ABA_PARECERES",
                            "formato_detectado": "parecer_estruturado_web",
                            "tamanho_bytes": len(rp_det.content),
                            "aprovado_gatekeeper": aprov,
                            "motivo_gatekeeper": mot,
                            "chars_uteis_corridos": chars_u,
                            "paragrafos_validos": parags,
                            "texto_util_preview": txt_corr[:350],
                        }
                        if aprov:
                            resultado["documentos_aprovados_gatekeeper"].append(doc_info)
                        else:
                            resultado["documentos_rejeitados_gatekeeper"].append(doc_info)
                except Exception:
                    pass

        # 3.3 Sonda Aba `TAs` (Termos Aditivos do Convênio - onde aparecem prorrogações por paralisação/atraso)
        url_tas = BASE_URL + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarTermosAditivos"
        r_tas = sess.get(url_tas, timeout=12)
        if r_tas.status_code == 200:
            soup_tas = BeautifulSoup(r_tas.text, "html.parser")
            links_ta = []
            for a in soup_tas.find_all("a"):
                href = a.get("href", "")
                if "ListaDeTermosAditivosDoConvenioDetalhar.do" in href or "TermosAditivos" in href:
                    m_t = re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", href)
                    if m_t:
                        tr = a.find_parent("tr")
                        desc_ta = tr.get_text(" | ", strip=True) if tr else "Termo Aditivo"
                        links_ta.append((desc_ta, m_t.group(1)))

            resultado["novos_endpoints_web"]["aba_termos_aditivos_count"] = len(links_ta)
            for idx_t, (desc_ta, path_ta) in enumerate(links_ta[:4], start=1):
                try:
                    rt_det = sess.get(BASE_URL + path_ta, timeout=12)
                    if rt_det.status_code == 200:
                        texto_ta = _extrair_texto_html_estruturado(rt_det.text, f"TERMO ADITIVO #{idx_t} ({desc_ta[:80]})")
                        aprov, mot, txt_corr, chars_u, parags, eh_em, eh_ht = avaliar_gatekeeper_anti_lixo(
                            texto_bruto=texto_ta,
                            formato="termo_aditivo_estruturado_web",
                            tamanho_bytes=len(rt_det.content),
                        )
                        doc_info = {
                            "nome_origem": f"TermoAditivo_Transferegov_{num_convenio}_{idx_t}.txt",
                            "endpoint_origem": "TRANSFEREGOV_ABA_TERMOS_ADITIVOS",
                            "formato_detectado": "termo_aditivo_estruturado_web",
                            "tamanho_bytes": len(rt_det.content),
                            "aprovado_gatekeeper": aprov,
                            "motivo_gatekeeper": mot,
                            "chars_uteis_corridos": chars_u,
                            "paragrafos_validos": parags,
                            "texto_util_preview": txt_corr[:350],
                        }
                        if aprov:
                            resultado["documentos_aprovados_gatekeeper"].append(doc_info)
                        else:
                            resultado["documentos_rejeitados_gatekeeper"].append(doc_info)
                except Exception:
                    pass

        # 3.4 Sonda Aba `Ajustes do PT` (Ajustes do Plano de Trabalho)
        url_apt = BASE_URL + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarObjeto/SelecionarObjeto.do?destino=ListarAjustePlanoTrabalho"
        r_apt = sess.get(url_apt, timeout=12)
        if r_apt.status_code == 200:
            soup_apt = BeautifulSoup(r_apt.text, "html.parser")
            links_apt = [
                re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", "")).group(1)
                for a in soup_apt.find_all("a")
                if re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", ""))
                and "ForwardAction" not in a.get("href", "")
            ]
            resultado["novos_endpoints_web"]["aba_ajustes_pt_count"] = len(links_apt)
            for idx_a, path_apt in enumerate(links_apt[:3], start=1):
                try:
                    ra_det = sess.get(BASE_URL + path_apt, timeout=12)
                    if ra_det.status_code == 200:
                        texto_apt = _extrair_texto_html_estruturado(ra_det.text, f"AJUSTE PLANO DE TRABALHO #{idx_a}")
                        aprov, mot, txt_corr, chars_u, parags, _, _ = avaliar_gatekeeper_anti_lixo(
                            texto_bruto=texto_apt,
                            formato="ajuste_pt_estruturado_web",
                            tamanho_bytes=len(ra_det.content),
                        )
                        doc_info = {
                            "nome_origem": f"AjustePT_Transferegov_{num_convenio}_{idx_a}.txt",
                            "endpoint_origem": "TRANSFEREGOV_ABA_AJUSTES_PT",
                            "formato_detectado": "ajuste_pt_estruturado_web",
                            "tamanho_bytes": len(ra_det.content),
                            "aprovado_gatekeeper": aprov,
                            "motivo_gatekeeper": mot,
                            "chars_uteis_corridos": chars_u,
                            "paragrafos_validos": parags,
                            "texto_util_preview": txt_corr[:350],
                        }
                        if aprov:
                            resultado["documentos_aprovados_gatekeeper"].append(doc_info)
                        else:
                            resultado["documentos_rejeitados_gatekeeper"].append(doc_info)
                except Exception:
                    pass

        # 3.5 Sonda Aba `Processo de Execução` (Licitações e Contratos anexados pelo convenente)
        url_lic = BASE_URL + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarLicitacoes"
        r_lic = sess.get(url_lic, timeout=12)
        if r_lic.status_code == 200:
            soup_lic = BeautifulSoup(r_lic.text, "html.parser")
            links_lic = [
                re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", "")).group(1)
                for a in soup_lic.find_all("a")
                if "ListarLicitacoesDetalhar.do" in a.get("href", "")
                and re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", ""))
            ]
            resultado["novos_endpoints_web"]["aba_licitacoes_execucao_count"] = len(links_lic)
            for idx_l, path_lic in enumerate(links_lic[:3], start=1):
                try:
                    rl_det = sess.get(BASE_URL + path_lic, timeout=12)
                    if rl_det.status_code == 200:
                        soup_ld = BeautifulSoup(rl_det.text, "html.parser")
                        # Verifica se há arquivos anexos na licitação/execução
                        dl_lic = [
                            re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", "")).group(1)
                            for a in soup_ld.find_all("a")
                            if ("Download" in a.get("href", "") or "Baixar" in a.get("href", ""))
                            and re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", ""))
                        ]
                        for idx_f, path_f in enumerate(dl_lic[:4], start=1):
                            rf = sess.get(BASE_URL + path_f, timeout=20)
                            if rf.status_code == 200 and rf.content:
                                cd = rf.headers.get("Content-Disposition", "")
                                m_fn = re.search(r'filename="?([^";]+)"?', cd)
                                nome_f = m_fn.group(1).strip() if m_fn else f"Execucao_Lic_{idx_l}_{idx_f}.bin"
                                docs_p, insp_z = ingerir_payload_multiformato(rf.content, nome_f)
                                if insp_z:
                                    resultado["zips_inspecionados"].append({
                                        "aba": "ABA_PROCESSO_EXECUCAO",
                                        "nome_zip": insp_z.nome_zip,
                                        "total_entradas": insp_z.total_entradas_zip,
                                        "ignorados": len(insp_z.entradas_ignoradas_engenharia_midia),
                                        "extraidos": len(insp_z.entradas_texto_rico_extraidas),
                                    })
                                for d in docs_p:
                                    info_d = d.to_summary_dict()
                                    info_d["endpoint_origem"] = "TRANSFEREGOV_ABA_PROCESSO_EXECUCAO"
                                    if d.aprovado_gatekeeper:
                                        resultado["documentos_aprovados_gatekeeper"].append(info_d)
                                    else:
                                        resultado["documentos_rejeitados_gatekeeper"].append(info_d)
                except Exception:
                    pass

        # 3.6 Sonda Aba `Relatórios de Execução`
        url_relex = BASE_URL + "/voluntarias/ForwardAction.do?modulo=proposta&path=/SelecionarConvenio/SelecionarConvenio.do?destino=ListarRelatoriosExecucao"
        r_relex = sess.get(url_relex, timeout=12)
        if r_relex.status_code == 200:
            soup_relex = BeautifulSoup(r_relex.text, "html.parser")
            links_relex = [
                re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", "")).group(1)
                for a in soup_relex.find_all("a")
                if "ListaDeRelatoriosVisualizar.do" in a.get("href", "")
                and re.search(r"['\"](/voluntarias/[^'\"]+)['\"]", a.get("href", ""))
            ]
            resultado["novos_endpoints_web"]["aba_relatorios_execucao_count"] = len(links_relex)

        # 3.7 Sonda Microsserviço de Acompanhamento de Obras (`medicao.transferegov.sistema.gov.br`)
        if resultado["id_proposta_interno"]:
            id_prop = resultado["id_proposta_interno"]
            try:
                r_med = sess.get(
                    f"https://medicao.transferegov.sistema.gov.br/medicao/acompanhamento/proposta/{id_prop}",
                    timeout=10,
                )
                resultado["novos_endpoints_web"]["aba_acompanhamento_obras_medicao_status"] = r_med.status_code
            except Exception as exc:
                resultado["novos_endpoints_web"]["aba_acompanhamento_obras_medicao_status"] = f"ERR:{type(exc).__name__}"

    except Exception as exc:
        resultado["erro_geral"] = str(exc)

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# 4. SONDAGEM PROFUNDA PNCP (CONTRATOS, TERMOS ADITIVOS/RESCISÕES E COMPRAS)
# ─────────────────────────────────────────────────────────────────────────────

class PNCPContractsIndex:
    """
    Constrói um índice local em memória dos contratos do DNIT no PNCP (2021-2024)
    via `/api/consulta/v1/contratos` para casar rapidamente pelo número do instrumento
    (ex.: `12 00271/2024` -> contrato `00271`, ano `2024`).
    """

    def __init__(self, cnpj: str = CNPJ_DNIT) -> None:
        self.cnpj = cnpj
        self.contratos_por_ano_num: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.total_contratos_indexados = 0

    def carregar_anos(self, anos: list[int]) -> None:
        sess = requests.Session()
        sess.headers.update(DEFAULT_HEADERS)
        for ano in anos:
            pagina = 1
            while True:
                url = (
                    f"https://pncp.gov.br/api/consulta/v1/contratos"
                    f"?dataInicial={ano}0101&dataFinal={ano}1231&cnpjOrgao={self.cnpj}"
                    f"&pagina={pagina}&tamanhoPagina=500"
                )
                try:
                    r = sess.get(url, timeout=20)
                    if r.status_code != 200:
                        break
                    payload = r.json()
                    items = payload.get("data") or []
                    for c in items:
                        num_emp = str(c.get("numeroContratoEmpenho") or "").strip()
                        if num_emp.upper().startswith("202") and "NE" in num_emp.upper():
                            continue
                        ano_c = str(c.get("anoContrato") or ano).strip()
                        # Extrai os dígitos finais do contrato (ex.: "00271" -> "271" ou "06 00766" -> "766")
                        partes_num = re.findall(r"\d+", num_emp)
                        digitos = partes_num[-1].lstrip("0") or "0" if partes_num else ""
                        if digitos:
                            self.contratos_por_ano_num.setdefault((ano_c, digitos), []).append(c)
                            self.total_contratos_indexados += 1
                    if payload.get("paginasRestantes", 0) <= 0 or not items:
                        break
                    pagina += 1
                except Exception:
                    break


def sondar_obra_pncp_profundo(
    obra: dict[str, Any],
    indice_contratos: PNCPContractsIndex,
) -> dict[str, Any]:
    """
    Sonda profundamente uma obra DNIT no PNCP:
    1. Localiza o Contrato em `/orgaos/{cnpj}/contratos/{ano}/{seq}`;
    2. Inspeciona `/contratos/{ano}/{seq}/arquivos` (Contrato assinado, anexos, etc.);
    3. Inspeciona `/contratos/{ano}/{seq}/termos` (Termos Aditivos, Termos de Rescisão, Apostilamentos)
       e `/termos/{seqTermo}/arquivos` + textos de `objetoTermoContrato` / `informativoObservacao`;
    4. Segue o link reverso `numeroControlePncpCompra` para `/compras/{anoCompra}/{seqCompra}/arquivos`,
       aplicando descompactação in-memory de `.zip` e leitura multiformato (`.docx`, `.odt`, `.rtf`, `.pdf`).
    """
    num_inst = str(obra.get("num_instrumento", "")).strip()
    emp_obra = _normalizar_ascii(obra.get("empreendimento", ""))

    # Extrai ano e número sequencial do contrato local (ex.: "12 00271/2024" -> num="271", ano="2024")
    m = re.search(r"(\d+)\s*/\s*(\d{4})", num_inst)
    num_curto = m.group(1).lstrip("0") if m else ""
    ano_inst = m.group(2) if m else ""

    resultado: dict[str, Any] = {
        "id_obra": obra["id"],
        "base": obra["base_de_dados"],
        "num_instrumento": num_inst,
        "sprint1_coletava": 0,  # Na Sprint 1, sem pncp_controle na planilha, verified_record retornava None (0 arquivos!)
        "contrato_pncp_encontrado": False,
        "contratos_candidatos_count": 0,
        "contrato_selecionado": None,
        "arquivos_contrato_count": 0,
        "termos_aditivos_rescisao_count": 0,
        "termos_detalhes": [],
        "arquivos_termos_count": 0,
        "compra_vinculada_controle": None,
        "arquivos_compra_vinculada_count": 0,
        "documentos_aprovados_gatekeeper": [],
        "documentos_rejeitados_gatekeeper": [],
        "zips_inspecionados": [],
    }

    candidatos = indice_contratos.contratos_por_ano_num.get((ano_inst, num_curto), [])
    resultado["contratos_candidatos_count"] = len(candidatos)
    if not candidatos:
        return resultado

    # Seleciona o candidato com maior interseção lexical com o objeto do empreendimento ou UF
    uf_obra = str(obra.get("local", "")).strip().upper()
    melhor_cand = candidatos[0]
    melhor_score = -1
    palavras_obra = {w for w in re.findall(r"[a-z0-9]{3,}", emp_obra)}
    for c in candidatos:
        obj_c = _normalizar_ascii(c.get("objetoContrato", ""))
        palavras_c = {w for w in re.findall(r"[a-z0-9]{3,}", obj_c)}
        inter = len(palavras_obra & palavras_c)
        uf_c = ((c.get("unidadeOrgao") or {}).get("ufSigla") or "").upper()
        if uf_obra and uf_c == uf_obra:
            inter += 10
        if inter > melhor_score:
            melhor_score = inter
            melhor_cand = c

    ano_c = melhor_cand.get("anoContrato")
    seq_c = melhor_cand.get("sequencialContrato")
    cnpj = indice_contratos.cnpj
    resultado["contrato_pncp_encontrado"] = True
    resultado["contrato_selecionado"] = {
        "numeroControlePNCP": melhor_cand.get("numeroControlePNCP"),
        "anoContrato": ano_c,
        "sequencialContrato": seq_c,
        "numeroContratoEmpenho": melhor_cand.get("numeroContratoEmpenho"),
        "processo": melhor_cand.get("processo"),
        "uf": (melhor_cand.get("unidadeOrgao") or {}).get("ufSigla"),
        "objetoContrato": (melhor_cand.get("objetoContrato") or "")[:250],
        "numeroControlePncpCompra": melhor_cand.get("numeroControlePncpCompra"),
    }

    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)

    # 1. Consultar arquivos diretos do Contrato (`/contratos/{ano}/{seq}/arquivos`)
    url_arq_c = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/{ano_c}/{seq_c}/arquivos"
    try:
        ra = sess.get(url_arq_c, timeout=15)
        if ra.status_code == 200 and isinstance(ra.json(), list):
            arqs_c = ra.json()
            resultado["arquivos_contrato_count"] = len(arqs_c)
            for idx_a, arq in enumerate(arqs_c[:6], start=1):
                link = arq.get("url") or arq.get("uri")
                titulo = arq.get("titulo") or arq.get("nomeOriginal") or f"Contrato_Arq_{idx_a}"
                tipo_doc = arq.get("tipoDocumentoNome") or "Contrato"
                if not link:
                    continue
                ok_v2, _ = filtro_pre_download_dom_v2(f"{tipo_doc} {titulo}")
                if not ok_v2:
                    continue
                rd = sess.get(link, timeout=30)
                if rd.status_code == 200 and rd.content:
                    docs_p, insp_z = ingerir_payload_multiformato(rd.content, titulo)
                    if insp_z:
                        resultado["zips_inspecionados"].append({
                            "endpoint": "PNCP_CONTRATO_ARQUIVOS",
                            "nome_zip": insp_z.nome_zip,
                            "total_entradas": insp_z.total_entradas_zip,
                            "ignorados": len(insp_z.entradas_ignoradas_engenharia_midia),
                            "extraidos": len(insp_z.entradas_texto_rico_extraidas),
                        })
                    for d in docs_p:
                        info_d = d.to_summary_dict()
                        info_d["endpoint_origem"] = "PNCP_CONTRATO_ARQUIVOS"
                        info_d["tipo_pncp"] = tipo_doc
                        if d.aprovado_gatekeeper:
                            resultado["documentos_aprovados_gatekeeper"].append(info_d)
                        else:
                            resultado["documentos_rejeitados_gatekeeper"].append(info_d)
    except Exception:
        pass

    # 2. Consultar Termos Aditivos / Rescisões / Apostilamentos (`/contratos/{ano}/{seq}/termos`)
    url_termos = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/{ano_c}/{seq_c}/termos"
    try:
        rt = sess.get(url_termos, timeout=15)
        if rt.status_code == 200 and isinstance(rt.json(), list):
            termos = rt.json()
            resultado["termos_aditivos_rescisao_count"] = len(termos)
            blocos_termos_texto: list[str] = []
            for t in termos:
                seq_t = t.get("sequencialTermoContrato")
                tipo_t = t.get("tipoTermoContratoNome") or "Termo"
                num_t = t.get("numeroTermoContrato") or ""
                data_t = t.get("dataAssinatura") or t.get("dataInclusao") or ""
                obj_t = t.get("objetoTermoContrato") or ""
                obs_t = t.get("informativoObservacao") or ""
                fund_t = t.get("fundamentoLegal") or ""

                resultado["termos_detalhes"].append({
                    "sequencialTermoContrato": seq_t,
                    "tipoTermoContratoNome": tipo_t,
                    "numeroTermoContrato": num_t,
                    "dataAssinatura": data_t,
                    "objetoTermoContrato": obj_t[:300],
                    "informativoObservacao": obs_t[:300],
                })

                blocos_termos_texto.append(
                    f"TERMO DE CONTRATO PNCP — {tipo_t} nº {num_t} (Data: {data_t})\n"
                    f"Processo SEI: {t.get('processo', '')} | Contrato: {melhor_cand.get('numeroContratoEmpenho', '')}\n"
                    f"Objeto do Termo / Justificativa: {obj_t}\n"
                    f"Observação Informativa / Motivação: {obs_t}\n"
                    f"Fundamento Legal: {fund_t}"
                )

                # Verifica se o Termo possui arquivos anexos (`/termos/{seq_t}/arquivos`)
                if seq_t is not None:
                    url_ta = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/{ano_c}/{seq_c}/termos/{seq_t}/arquivos"
                    rta = sess.get(url_ta, timeout=12)
                    if rta.status_code == 200 and isinstance(rta.json(), list):
                        arqs_t = rta.json()
                        resultado["arquivos_termos_count"] += len(arqs_t)
                        for idx_ta, arq_t in enumerate(arqs_t[:4], start=1):
                            link_ta = arq_t.get("url") or arq_t.get("uri")
                            tit_ta = arq_t.get("titulo") or arq_t.get("nomeOriginal") or f"Termo_{seq_t}_{idx_ta}"
                            if not link_ta:
                                continue
                            rd_ta = sess.get(link_ta, timeout=25)
                            if rd_ta.status_code == 200 and rd_ta.content:
                                docs_p, insp_z = ingerir_payload_multiformato(rd_ta.content, tit_ta)
                                if insp_z:
                                    resultado["zips_inspecionados"].append({
                                        "endpoint": "PNCP_TERMOS_ARQUIVOS",
                                        "nome_zip": insp_z.nome_zip,
                                        "total_entradas": insp_z.total_entradas_zip,
                                        "ignorados": len(insp_z.entradas_ignoradas_engenharia_midia),
                                        "extraidos": len(insp_z.entradas_texto_rico_extraidas),
                                    })
                                for d in docs_p:
                                    info_d = d.to_summary_dict()
                                    info_d["endpoint_origem"] = f"PNCP_TERMO_{tipo_t.upper()}"
                                    if d.aprovado_gatekeeper:
                                        resultado["documentos_aprovados_gatekeeper"].append(info_d)
                                    else:
                                        resultado["documentos_rejeitados_gatekeeper"].append(info_d)

            # Consolida também o histórico completo de Termos Aditivos / Rescisões do contrato caso atinja >= 800 chars úteis
            if blocos_termos_texto:
                texto_consolidado_termos = (
                    f"HISTÓRICO OFICIAL DE TERMOS ADITIVOS E RESCISÕES DO CONTRATO {melhor_cand.get('numeroContratoEmpenho')} "
                    f"(PROCESSO {melhor_cand.get('processo')}) — OBJETO: {melhor_cand.get('objetoContrato')}\n\n"
                    + "\n\n".join(blocos_termos_texto)
                )
                aprov, mot, txt_corr, chars_u, parags, _, _ = avaliar_gatekeeper_anti_lixo(
                    texto_bruto=texto_consolidado_termos,
                    formato="pncp_termos_json",
                    tamanho_bytes=len(texto_consolidado_termos.encode("utf-8")),
                )
                info_hist = {
                    "nome_origem": f"Historico_Termos_PNCP_{ano_c}_{seq_c}.json",
                    "endpoint_origem": "PNCP_CONTRATO_TERMOS_HISTORICO",
                    "formato_detectado": "pncp_termos_json",
                    "tamanho_bytes": len(texto_consolidado_termos.encode("utf-8")),
                    "aprovado_gatekeeper": aprov,
                    "motivo_gatekeeper": mot,
                    "chars_uteis_corridos": chars_u,
                    "paragrafos_validos": parags,
                    "texto_util_preview": txt_corr[:350],
                }
                if aprov:
                    resultado["documentos_aprovados_gatekeeper"].append(info_hist)
                else:
                    resultado["documentos_rejeitados_gatekeeper"].append(info_hist)
    except Exception:
        pass

    # 3. Seguir link reverso para a Compra vinculada (`numeroControlePncpCompra`)
    ctrl_compra = melhor_cand.get("numeroControlePncpCompra")
    resultado["compra_vinculada_controle"] = ctrl_compra
    if isinstance(ctrl_compra, str):
        m_comp = re.fullmatch(r"(\d{14})-1-(\d+)/(\d{4})", ctrl_compra.strip())
        if m_comp:
            cnpj_comp, seq_comp_raw, ano_comp = m_comp.groups()
            seq_comp = str(int(seq_comp_raw))
            url_comp_arqs = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj_comp}/compras/{ano_comp}/{seq_comp}/arquivos"
            try:
                rc = sess.get(url_comp_arqs, timeout=15)
                if rc.status_code == 200 and isinstance(rc.json(), list):
                    arqs_comp = rc.json()
                    resultado["arquivos_compra_vinculada_count"] = len(arqs_comp)
                    for idx_c, arq_c in enumerate(arqs_comp[:6], start=1):
                        link_c = arq_c.get("url") or arq_c.get("uri")
                        tit_c = arq_c.get("titulo") or arq_c.get("nomeOriginal") or f"Compra_Arq_{idx_c}"
                        tipo_c = arq_c.get("tipoDocumentoNome") or "DocumentoCompra"
                        if not link_c:
                            continue
                        ok_v2, _ = filtro_pre_download_dom_v2(f"{tipo_c} {tit_c}")
                        if not ok_v2:
                            continue
                        rd_c = sess.get(link_c, timeout=35)
                        if rd_c.status_code == 200 and rd_c.content:
                            docs_p, insp_z = ingerir_payload_multiformato(rd_c.content, tit_c)
                            if insp_z:
                                resultado["zips_inspecionados"].append({
                                    "endpoint": "PNCP_COMPRA_VINCULADA_ARQUIVOS",
                                    "nome_zip": insp_z.nome_zip,
                                    "total_entradas": insp_z.total_entradas_zip,
                                    "ignorados": len(insp_z.entradas_ignoradas_engenharia_midia),
                                    "extraidos": len(insp_z.entradas_texto_rico_extraidas),
                                })
                            for d in docs_p:
                                info_d = d.to_summary_dict()
                                info_d["endpoint_origem"] = "PNCP_COMPRA_VINCULADA_POR_CONTRATO"
                                info_d["tipo_pncp"] = tipo_c
                                if d.aprovado_gatekeeper:
                                    resultado["documentos_aprovados_gatekeeper"].append(info_d)
                                else:
                                    resultado["documentos_rejeitados_gatekeeper"].append(info_d)
            except Exception:
                pass

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# 5. SONDAGEM PROFUNDA SIMEC (OBRAS 2.0) E SISMOB CIDADÃO (API PÚBLICA)
# ─────────────────────────────────────────────────────────────────────────────

def sondar_obra_simec_obras2(obra: dict[str, Any]) -> dict[str, Any]:
    """
    Sonda o portal público do SIMEC Obras 2.0 (`simec.mec.gov.br/painelObras` e `simec.mec.gov.br/obras2`)
    para uma obra paralisada do FNDE/MEC (`obrid`).
    Verifica acesso às abas de Restrições e Inconformidades, Vistorias/Supervisão e Documentos Anexos,
    registrando se há bloqueio por reCAPTCHA ou autenticação obrigatória.
    """
    id_obra = str(obra.get("id", "")).strip()
    obrid = re.sub(r"\D", "", id_obra)
    local_str = str(obra.get("local", ""))
    uf = local_str.split("/")[-1].strip().upper() if "/" in local_str else ""

    sess = requests.Session()
    sess.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })

    resultado: dict[str, Any] = {
        "id_obra": id_obra,
        "obrid": obrid,
        "uf": uf,
        "sprint1_coletava": "Apenas Ficha Sintética FPDF (1,4 KB) — expurgada na Sprint 7 por vazamento",
        "endpoints_sondados": [],
        "bloqueio_recaptcha_detectado": False,
        "bloqueio_autenticacao_obras2_detectado": False,
        "documentos_aprovados_gatekeeper": [],
    }

    rotas_simec = [
        ("PAINEL_OBRAS_FICHA", f"https://simec.mec.gov.br/painelObras/dadosobra.php?obra={obrid}"),
        ("PAINEL_OBRAS_LISTA_UF", f"https://simec.mec.gov.br/painelObras/lista.php?estuf={uf}&obrid={obrid}"),
        ("OBRAS2_POPUP_RESTRICOES", f"https://simec.mec.gov.br/obras2/obras2.php?modulo=principal/cadObra&acao=A&obrid={obrid}"),
        ("OBRAS2_VISTORIAS_SUPERVISAO", f"https://simec.mec.gov.br/obras2/obras2.php?modulo=principal/listaSupervisao&acao=A&obrid={obrid}"),
        ("OBRAS2_DOCUMENTOS_ANEXOS", f"https://simec.mec.gov.br/obras2/obras2.php?modulo=principal/cadObraDocumentos&acao=A&obrid={obrid}"),
    ]

    for nome_rota, url in rotas_simec:
        try:
            r = sess.get(url, timeout=12, allow_redirects=True)
            txt_lower = r.text.lower()
            tem_recaptcha = "g-recaptcha" in txt_lower or "recaptcha" in txt_lower
            tem_login = "login.php" in r.url.lower() or "usuário" in txt_lower and "senha" in txt_lower and "autenticação" in txt_lower
            if tem_recaptcha:
                resultado["bloqueio_recaptcha_detectado"] = True
            if tem_login or "acesso negado" in txt_lower or len(r.text.strip()) < 200:
                resultado["bloqueio_autenticacao_obras2_detectado"] = True

            # Procura links de download de arquivos (arqid=...)
            links_arq = re.findall(r"arqid=(\d+)", r.text)
            resultado["endpoints_sondados"].append({
                "rota": nome_rota,
                "url": url,
                "url_final": r.url,
                "status_code": r.status_code,
                "bytes_resposta": len(r.content),
                "tem_recaptcha": tem_recaptcha,
                "redirecionado_login_ou_vazio": tem_login or len(r.text.strip()) < 200,
                "links_arqid_encontrados": len(links_arq),
            })
        except Exception as exc:
            resultado["endpoints_sondados"].append({
                "rota": nome_rota,
                "url": url,
                "erro": str(exc),
            })

    return resultado


def sondar_obra_sismob_api(obra: dict[str, Any], cache_municipios_ibge: dict[str, str]) -> dict[str, Any]:
    """
    Sonda a API pública oficial do SISMOB Cidadão (`https://sismobcidadao.saude.gov.br/api/public/...`):
    1. Resolve o código IBGE de 6 dígitos do município via `/api/public/endereco/municipios?ufIbge={uf_cod}&query={mun}`;
    2. Lista as obras do município em `/api/public/obras?municipioIbge={ibge6}&page=0&size=100` e casa pelo número da proposta / estabelecimento;
    3. Consulta o endpoint de detalhe `/api/public/obras/{propostaId}` para inspecionar `dsJustificativa`,
       `dtMudancaSituacao`, `dadosExecucao`, `empresas` e `gruposFotografias`.
    """
    id_obra = str(obra.get("id", "")).strip()
    num_proposta_alvo = id_obra.replace("SISMOB-", "").strip()
    local_str = str(obra.get("local", "")).strip()
    mun_nome, uf_sigla = (local_str.split("/", 1) + [""])[:2] if "/" in local_str else (local_str, "")
    mun_nome = mun_nome.strip()
    uf_sigla = uf_sigla.strip().upper()

    MAPA_UF_IBGE = {
        "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
        "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28", "BA": "29",
        "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41", "SC": "42", "RS": "43",
        "MS": "50", "MT": "51", "GO": "52", "DF": "53",
    }
    uf_cod = MAPA_UF_IBGE.get(uf_sigla, "")

    sess = requests.Session()
    sess.headers.update(DEFAULT_HEADERS)

    resultado: dict[str, Any] = {
        "id_obra": id_obra,
        "numero_proposta_extraido_id": num_proposta_alvo,
        "local": local_str,
        "sprint1_coletava": "Apenas Ficha Sintética FPDF — expurgada na Sprint 7 por vazamento",
        "ibge_6_resolvido": None,
        "proposta_id_encontrada": None,
        "detalhe_obra_api": None,
        "possui_ds_justificativa": False,
        "possui_anexos_pdf_docx": False,
        "documentos_aprovados_gatekeeper": [],
        "documentos_rejeitados_gatekeeper": [],
    }

    if not uf_cod or not mun_nome:
        return resultado

    chave_mun = f"{uf_sigla}:{_normalizar_ascii(mun_nome)}"
    ibge6 = cache_municipios_ibge.get(chave_mun)
    if not ibge6:
        try:
            rm = sess.get(
                "https://sismobcidadao.saude.gov.br/api/public/endereco/municipios",
                params={"ufIbge": uf_cod, "query": _normalizar_ascii(mun_nome).upper(), "pageSize": 20},
                timeout=12,
            )
            if rm.status_code == 200 and isinstance(rm.json(), list):
                for item_m in rm.json():
                    if _normalizar_ascii(item_m.get("nome", "")) == _normalizar_ascii(mun_nome):
                        ibge6 = str(item_m.get("ibge", ""))
                        break
                if not ibge6 and rm.json():
                    ibge6 = str(rm.json()[0].get("ibge", ""))
                if ibge6:
                    cache_municipios_ibge[chave_mun] = ibge6
        except Exception:
            pass

    resultado["ibge_6_resolvido"] = ibge6
    if not ibge6:
        return resultado

    # Busca obras do município na API pública do SISMOB
    try:
        ro = sess.get(
            "https://sismobcidadao.saude.gov.br/api/public/obras",
            params={"municipioIbge": ibge6, "page": 0, "size": 200},
            timeout=15,
        )
        if ro.status_code == 200:
            content = ro.json().get("content") or []
            cand_match = None
            for item_o in content:
                num_p = re.sub(r"\D", "", str(item_o.get("numeroProposta") or ""))
                if num_p == num_proposta_alvo:
                    cand_match = item_o
                    break
            if not cand_match:
                # Fallback por nome do empreendimento no mesmo município
                emp_alvo = _normalizar_ascii(obra.get("empreendimento", ""))
                for item_o in content:
                    nome_est = _normalizar_ascii(item_o.get("nomeEstabelecimento") or item_o.get("titulo") or "")
                    if emp_alvo and nome_est and (emp_alvo in nome_est or nome_est in emp_alvo):
                        cand_match = item_o
                        break

            if cand_match and cand_match.get("propostaId"):
                prop_id = cand_match["propostaId"]
                resultado["proposta_id_encontrada"] = prop_id
                rd = sess.get(f"https://sismobcidadao.saude.gov.br/api/public/obras/{prop_id}", timeout=15)
                if rd.status_code == 200:
                    det = rd.json()
                    just = det.get("dsJustificativa")
                    resultado["possui_ds_justificativa"] = bool(just and str(just).strip())
                    resultado["detalhe_obra_api"] = {
                        "propostaId": prop_id,
                        "nuProposta": det.get("nuProposta"),
                        "dsSituacaoObra": det.get("dsSituacaoObra"),
                        "dtMudancaSituacao": det.get("dtMudancaSituacao"),
                        "dsJustificativa": just,
                        "dtAtualizacao": det.get("dtAtualizacao"),
                        "percentualExecucao": det.get("percentualExecucao"),
                        "qtd_empresas": len(det.get("empresas") or []),
                        "qtd_grupos_fotografias": len(det.get("gruposFotografias") or []),
                    }
                    # Se houver justificativa textual longa na API, avalia no Gatekeeper
                    if just and len(str(just).strip()) > 0:
                        aprov, mot, txt_corr, chars_u, parags, _, _ = avaliar_gatekeeper_anti_lixo(
                            texto_bruto=str(just),
                            formato="sismob_api_json",
                            tamanho_bytes=len(rd.content),
                        )
                        info_s = {
                            "nome_origem": f"SISMOB_API_{prop_id}.json",
                            "endpoint_origem": "SISMOB_API_PUBLICA_OBRAS",
                            "formato_detectado": "sismob_api_json",
                            "tamanho_bytes": len(rd.content),
                            "aprovado_gatekeeper": aprov,
                            "motivo_gatekeeper": mot,
                            "chars_uteis_corridos": chars_u,
                            "paragrafos_validos": parags,
                            "texto_util_preview": txt_corr[:350],
                        }
                        if aprov:
                            resultado["documentos_aprovados_gatekeeper"].append(info_s)
                        else:
                            resultado["documentos_rejeitados_gatekeeper"].append(info_s)
    except Exception as exc:
        resultado["erro"] = str(exc)

    return resultado
