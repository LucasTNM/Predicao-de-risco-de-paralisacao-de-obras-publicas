# -*- coding: utf-8 -*-
"""
src/extractors/pncp.py
======================
Extrator e coletor profundo v2 de documentos oficiais via API do Portal Nacional de
Contratações Públicas (PNCP) para DNIT, CODEVASF e outros entes federais.

Melhorias da Reengenharia de Coleta (Feature 021):
1. `PNCPContractsIndex`: Resolve contratos oficiais via `/api/consulta/v1/contratos`
   cruzando ano, número do contrato, UF e similaridade lexical do empreendimento,
   sem jamais converter cegamente números locais em sequenciais de compra (`fail-closed` preservado).
2. Coleta em 3 níveis no PNCP:
   - Nível 1: Termos de Contrato / Aditivos / Rescisões (`/contratos/{ano}/{seq}/termos` e `/termos/{seqTermo}/arquivos`)
   - Nível 2: Arquivos do Contrato (`/contratos/{ano}/{seq}/arquivos`)
   - Nível 3: Compra Vinculada (`numeroControlePncpCompra` -> `/compras/{anoCompra}/{seqCompra}/arquivos`)
3. Ingestão Multiformato (`.pdf`, `.docx`, `.odt`, `.rtf`) e Descompactação Cirúrgica In-Memory de `.zip`
   (`ZipFile.infolist()`), eliminando a corrupção de arquivos `.zip` do DNIT que na Sprint 1 eram renomeados como `.pdf`.
4. Gatekeeper Anti-Lixo (>= 800 caracteres úteis + bloqueio regex de comprovantes de e-mail).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import threading
import time
import unicodedata
from typing import Any

import pandas as pd
import requests

from src.config import ARQUIVO_LOG_COLETA, DEFAULT_HEADERS, ROOT_DIR, logger
from src.extractors.pncp_identity import parse_control, verified_record
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


def _normalizar_ascii(texto: Any) -> str:
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("ASCII").lower().strip()


class PNCPContractsIndex:
    """
    Índice thread-safe em memória de contratos de um órgão no PNCP (`/api/consulta/v1/contratos`),
    permitindo resolver `num. instrumento` (ex.: `12 00271/2024`) para o `sequencialContrato`
    e `numeroControlePncpCompra` verificados.
    """

    def __init__(self, cnpj: str, anos: list[int] | None = None) -> None:
        self.cnpj = cnpj
        self.contratos_por_ano_num: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.total_contratos_indexados = 0
        self._anos_carregados: set[int] = set()
        self._lock = threading.Lock()
        if anos:
            self.carregar_anos(anos)

    def _indexar_itens(self, items: list[dict[str, Any]], ano_default: int | str) -> None:
        for c in items:
            if not isinstance(c, dict):
                continue
            num_emp = str(c.get("numeroContratoEmpenho") or "").strip()
            if num_emp.upper().startswith("202") and "NE" in num_emp.upper():
                continue
            ano_c = str(c.get("anoContrato") or ano_default).strip()
            partes_num = re.findall(r"\d+", num_emp)
            digitos = partes_num[-1].lstrip("0") or "0" if partes_num else ""
            if digitos:
                self.contratos_por_ano_num.setdefault((ano_c, digitos), []).append(c)
                self.total_contratos_indexados += 1

    def carregar_anos(self, anos: list[int]) -> None:
        with self._lock:
            anos_pendentes = [a for a in anos if a not in self._anos_carregados]
            if not anos_pendentes:
                return

            pasta_cache = ROOT_DIR / "logs" / "cache_pncp"
            pasta_cache.mkdir(parents=True, exist_ok=True)

            sess = requests.Session()
            sess.headers.update(DEFAULT_HEADERS)
            try:
                for ano in anos_pendentes:
                    arq_cache = pasta_cache / f"contratos_{self.cnpj}_{ano}.json"
                    if arq_cache.exists() and arq_cache.stat().st_size > 10:
                        try:
                            cached_items = json.loads(arq_cache.read_text(encoding="utf-8"))
                            if isinstance(cached_items, list) and cached_items:
                                self._indexar_itens(cached_items, ano)
                                self._anos_carregados.add(ano)
                                continue
                        except Exception:
                            pass

                    pagina = 1
                    itens_ano: list[dict[str, Any]] = []
                    completo_ano = True
                    while True:
                        url = (
                            f"https://pncp.gov.br/api/consulta/v1/contratos"
                            f"?dataInicial={ano}0101&dataFinal={ano}1231&cnpjOrgao={self.cnpj}"
                            f"&pagina={pagina}&tamanhoPagina=500"
                        )
                        sucesso_pag = False
                        payload: dict[str, Any] = {}
                        for tentativa in range(4):
                            try:
                                r = sess.get(url, timeout=25)
                                if r.status_code == 200:
                                    payload = r.json()
                                    sucesso_pag = True
                                    break
                                if r.status_code in (429, 500, 502, 503, 504):
                                    time.sleep(1.5 * (2**tentativa))
                                    continue
                                break
                            except Exception:
                                time.sleep(1.0 * (tentativa + 1))

                        if not sucesso_pag:
                            completo_ano = False
                            break

                        items = payload.get("data") or []
                        itens_ano.extend(items)
                        self._indexar_itens(items, ano)

                        if payload.get("paginasRestantes", 0) <= 0 or not items:
                            break
                        pagina += 1
                        time.sleep(0.15)

                    if completo_ano and itens_ano:
                        try:
                            arq_cache.write_text(json.dumps(itens_ano, ensure_ascii=False), encoding="utf-8")
                        except Exception:
                            pass
                    self._anos_carregados.add(ano)
            finally:
                sess.close()

    def resolver_contrato(self, row: pd.Series | dict[str, Any]) -> dict[str, Any] | None:
        """
        Localiza o contrato oficial no PNCP a partir de `num. instrumento`, `empreendimento` e `local`.
        Carrega sob demanda o ano do instrumento caso ainda não esteja indexado.
        """
        num_inst = re.sub(r"\.0+$", "", str(row.get("num. instrumento", "")).strip())
        m = re.search(r"(\d+)\s*/\s*(\d{4})", num_inst)
        if not m:
            return None
        num_curto = m.group(1).lstrip("0") or "0"
        ano_inst = m.group(2)

        ano_int = int(ano_inst)
        if ano_int not in self._anos_carregados and 2020 <= ano_int <= 2026:
            self.carregar_anos([ano_int])

        candidatos = self.contratos_por_ano_num.get((ano_inst, num_curto), [])
        if not candidatos:
            return None

        emp_obra = _normalizar_ascii(row.get("empreendimento", ""))
        local_str = str(row.get("local", "")).strip().upper()
        uf_obra = local_str.split("/")[-1].strip() if "/" in local_str else local_str
        palavras_obra = {w for w in re.findall(r"[a-z0-9]{3,}", emp_obra)}

        melhor_cand = candidatos[0]
        melhor_score = -1
        for c in candidatos:
            obj_c = _normalizar_ascii(c.get("objetoContrato", ""))
            palavras_c = {w for w in re.findall(r"[a-z0-9]{3,}", obj_c)}
            score = len(palavras_obra & palavras_c)
            uf_c = ((c.get("unidadeOrgao") or {}).get("ufSigla") or "").upper()
            if uf_obra and uf_c == uf_obra:
                score += 10
            if score > melhor_score:
                melhor_score = score
                melhor_cand = c

        ano_c = str(melhor_cand.get("anoContrato") or ano_inst)
        seq_c = str(melhor_cand.get("sequencialContrato") or "")
        if not seq_c:
            return None

        control = melhor_cand.get("numeroControlePNCP") or f"{self.cnpj}-2-{int(seq_c):06d}/{ano_c}"
        return {
            "cnpj": self.cnpj,
            "kind": "contratos",
            "year": ano_c,
            "sequence": seq_c,
            "url": f"https://pncp.gov.br/api/pncp/v1/orgaos/{self.cnpj}/contratos/{ano_c}/{seq_c}",
            "control": control,
            "metadata": melhor_cand,
        }


def pontuar_arquivo_pncp(item: dict[str, Any]) -> int:
    """
    Classifica a prioridade de download do arquivo PNCP baseando-se em sua tipologia,
    priorizando Termos Aditivos, Rescisões, Pareceres, Projetos Básicos, Memoriais, TRs e Editais.
    """
    tipo = (item.get("tipoDocumentoNome") or "").lower()
    titulo = (item.get("titulo") or item.get("nomeOriginal") or "").lower()
    combinado = f"{tipo} {titulo}"

    score = 0
    if any(k in combinado for k in ("rescisão", "rescisao", "paralisação", "paralisacao", "suspensão")):
        score += 130
    if "termo aditivo" in combinado or "aditivo" in combinado or "apostilamento" in combinado:
        score += 120
    if any(k in combinado for k in ("parecer", "nota técnica", "nota tecnica", "laudo", "vistoria")):
        score += 110
    if "edital" in combinado:
        score += 100
    if "termo de referência" in combinado or "termo de referencia" in combinado:
        score += 95
    if "projeto" in combinado or "memorial" in combinado:
        score += 90
    if "contrato" in combinado or "termo de compromisso" in combinado:
        score += 85
    if "estudo técnico" in combinado or "estudo tecnico" in combinado:
        score += 80
    if "ato que autoriza" in combinado or "despacho" in combinado:
        score += 60

    if re.search(r"edital|termo|estudo|projeto|contrato|nota|mapa|aviso|parecer|memorial|aditivo", titulo, re.I):
        score += 25
    if re.search(r"planilha|orçamento|cronograma|resultado", titulo, re.I):
        score -= 20
    return score


def _comitar_doc_pncp(
    *,
    doc: DocumentoProcessado,
    caminho_arquivo: Path,
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
    if not doc.aprovado_gatekeeper:
        return None

    obra_hashes = cache_hashes.setdefault(id_obra, set())
    if doc.sha256 and doc.sha256 in obra_hashes:
        return None
    if doc.sha256:
        obra_hashes.add(doc.sha256)

    if not arquivo_ja_existe_valido(caminho_arquivo):
        ok = materializar_documento_aprovado_em_pdf(
            doc=doc,
            caminho_destino=caminho_arquivo,
            titulo_cabecalho=titulo_cabecalho,
        )
        if not ok or not arquivo_ja_existe_valido(caminho_arquivo):
            return None

    avaliacao = validar_e_registrar_pdf(
        caminho_pdf=caminho_arquivo,
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
        return caminho_arquivo
    return None


def _processar_lista_arquivos_pncp(
    *,
    sess: requests.Session,
    arquivos_api: list[dict[str, Any]],
    prefixo_nome: str,
    url_origem: str,
    control_id: str,
    base_nome: str,
    id_obra: str,
    num_inst: str,
    emp: str,
    pasta_destino: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]],
    caminho_csv: Path,
    max_arquivos: int = 8,
) -> tuple[list[Path], int, int, int]:
    """
    Processa uma lista de metadados de arquivos retornada por um endpoint PNCP
    (`/contratos/.../arquivos`, `/termos/.../arquivos` ou `/compras/.../arquivos`),
    com descompactação in-memory de `.zip` e Gatekeeper Anti-Lixo.
    """
    candidatos = []
    for arq in arquivos_api:
        if not isinstance(arq, dict):
            continue
        score = pontuar_arquivo_pncp(arq)
        link = arq.get("url") or arq.get("uri")
        if link and score >= 0:
            candidatos.append((score, arq))

    candidatos.sort(key=lambda x: x[0], reverse=True)
    validados: list[Path] = []
    filtrados_meta = filtrados_poda = zips_abertos = 0

    for idx, (score, arq) in enumerate(candidatos[:max_arquivos], start=1):
        link = arq.get("url") or arq.get("uri")
        tipo_nome = arq.get("tipoDocumentoNome") or f"DOC_{idx}"
        titulo_doc = arq.get("titulo") or arq.get("nomeOriginal") or f"Arq_{idx}"
        texto_meta = f"{tipo_nome} {titulo_doc}"

        deve_baixar, motivo_filtro = filtro_pre_download_dom(texto_meta)
        if not deve_baixar:
            filtrados_meta += 1
            logger.debug(f"    [FILTRO API] {texto_meta[:45]} -> BLOQUEADO ({motivo_filtro})")
            continue

        try:
            r_down = sess.get(link, timeout=45)
            if r_down.status_code != 200 or not r_down.content:
                continue

            cd = r_down.headers.get("Content-Disposition", "")
            m_fn = re.search(r'filename="?([^";]+)"?', cd)
            nome_real = m_fn.group(1).strip() if m_fn else titulo_doc

            docs_proc, insp_zip = ingerir_payload_multiformato(r_down.content, nome_real)
            if insp_zip:
                zips_abertos += 1

            for sub_idx, doc_item in enumerate(docs_proc, start=1):
                if not doc_item.aprovado_gatekeeper:
                    filtrados_poda += 1
                    continue
                sufixo = re.sub(r"[^A-Za-z0-9]", "_", Path(doc_item.nome_origem).stem)[:30]
                nome_arquivo = (
                    f"{prefixo_nome}_{idx}_{sub_idx}_{sufixo}.pdf"
                    if len(docs_proc) > 1
                    else f"{prefixo_nome}_{idx}_{sufixo}.pdf"
                )
                caminho_arquivo = pasta_destino / nome_arquivo
                salvo = _comitar_doc_pncp(
                    doc=doc_item,
                    caminho_arquivo=caminho_arquivo,
                    titulo_cabecalho=f"DOCUMENTO OFICIAL PNCP ({tipo_nome}) — {doc_item.nome_origem}",
                    base_nome=base_nome,
                    id_obra=id_obra,
                    num_inst=num_inst,
                    emp=emp,
                    obs_extra=f"Score PNCP: {score} | Tipo API: {tipo_nome} | Controle: {control_id} | Fonte: {url_origem}",
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    caminho_csv=caminho_csv,
                )
                if salvo:
                    validados.append(salvo)
        except Exception as exc_dl:
            logger.debug(f"    [ERRO REDE PNCP] Falha ao baixar {link}: {exc_dl}")
            continue

    return validados, filtrados_meta, filtrados_poda, zips_abertos


def coletar_obra_pncp(
    sess: requests.Session,
    cnpj: str,
    base_nome: str,
    ano: str,
    seq: str,
    row: pd.Series | dict[str, Any],
    pasta_destino: Path,
    cache_log: dict[tuple[str, str, str], str] | set[tuple[str, str, str]],
    cache_hashes: dict[str, set[str]] | None = None,
    indice_contratos: PNCPContractsIndex | None = None,
    caminho_csv: Path = ARQUIVO_LOG_COLETA,
) -> list[Path]:
    """
    Consulta a API do PNCP em 3 níveis (Termos Aditivos/Rescisões, Arquivos do Contrato e
    Arquivos da Compra Vinculada), aplicando descompactação cirúrgica de `.zip` in-memory,
    ingestão multiformato (`.pdf`, `.docx`, `.odt`, `.rtf`) e Gatekeeper Anti-Lixo (>= 800 chars).
    """
    id_obra = str(row.get("id", "")).strip()
    emp = str(row.get("empreendimento", "")).strip()
    num_inst = str(row.get("num. instrumento", "")).strip()

    # 1. Identidade Fail-Closed: primeiro tenta `verified_record` explícito; se ausente, usa `indice_contratos`
    identity = verified_record(sess, cnpj, row)
    if identity is None and indice_contratos is not None:
        identity = indice_contratos.resolver_contrato(row)

    if identity is None:
        logger.debug(f"  [{base_nome} {id_obra}] PNCP: identidade não confirmada; coleta pendente.")
        return []

    ano_id, seq_id = str(identity["year"]), str(identity["sequence"])
    kind = identity["kind"]
    control_id = str(identity.get("control") or f"{cnpj}-{ano_id}-{seq_id}")
    meta_contrato = identity.get("metadata") or {}

    if cache_hashes is None:
        cache_hashes = {}

    arquivos_validados: list[Path] = []
    tot_meta = tot_poda = tot_zips = 0

    try:
        # ─── NÍVEL 1: TERMOS DE CONTRATO / ADITIVOS / RESCISÕES (SE FOR CONTRATO) ─
        if kind == "contratos":
            url_termos = f"{identity['url']}/termos"
            try:
                rt = sess.get(url_termos, headers={"Accept": "application/json"}, timeout=15)
                if rt.status_code == 200:
                    termos = rt.json()
                    if isinstance(termos, list) and termos:
                        blocos_termos: list[str] = []
                        for t in termos:
                            if not isinstance(t, dict):
                                continue
                            seq_t = t.get("sequencialTermoContrato")
                            tipo_t = t.get("tipoTermoContratoNome") or "Termo"
                            num_t = t.get("numeroTermoContrato") or ""
                            data_t = t.get("dataAssinatura") or t.get("dataInclusao") or ""
                            obj_t = t.get("objetoTermoContrato") or ""
                            obs_t = t.get("informativoObservacao") or ""
                            fund_t = t.get("fundamentoLegal") or ""

                            blocos_termos.append(
                                f"TERMO DE CONTRATO PNCP — {tipo_t} nº {num_t} (Data: {data_t})\n"
                                f"Processo SEI: {t.get('processo', '')} | Contrato: {meta_contrato.get('numeroContratoEmpenho', num_inst)}\n"
                                f"Objeto / Justificativa: {obj_t}\n"
                                f"Motivação / Observação: {obs_t}\n"
                                f"Fundamento Legal: {fund_t}"
                            )

                            # Arquivos anexados diretamente ao Termo Aditivo / Rescisão
                            if seq_t is not None:
                                url_arq_t = f"{url_termos}/{seq_t}/arquivos"
                                rta = sess.get(url_arq_t, headers={"Accept": "application/json"}, timeout=12)
                                if rta.status_code == 200 and isinstance(rta.json(), list):
                                    vals_t, fm, fp, fz = _processar_lista_arquivos_pncp(
                                        sess=sess,
                                        arquivos_api=rta.json(),
                                        prefixo_nome=f"{base_nome}_termo_{ano_id}_{seq_id}_{seq_t}",
                                        url_origem=url_arq_t,
                                        control_id=control_id,
                                        base_nome=base_nome,
                                        id_obra=id_obra,
                                        num_inst=num_inst,
                                        emp=emp,
                                        pasta_destino=pasta_destino,
                                        cache_log=cache_log,
                                        cache_hashes=cache_hashes,
                                        caminho_csv=caminho_csv,
                                    )
                                    arquivos_validados.extend(vals_t)
                                    tot_meta += fm
                                    tot_poda += fp
                                    tot_zips += fz

                        # Consolida histórico textual dos Termos Aditivos e Rescisões se >= 800 chars úteis
                        if blocos_termos:
                            texto_hist = (
                                f"HISTÓRICO OFICIAL DE TERMOS ADITIVOS E RESCISÕES DO CONTRATO {meta_contrato.get('numeroContratoEmpenho', num_inst)} "
                                f"(PROCESSO {meta_contrato.get('processo', '')}) — OBJETO: {meta_contrato.get('objetoContrato', emp)}\n\n"
                                + "\n\n".join(blocos_termos)
                            )
                            raw_h = texto_hist.encode("utf-8", errors="replace")
                            aprov, mot, txt_corr, chars_u, parags, eh_em, eh_ht = avaliar_gatekeeper_anti_lixo(
                                texto_bruto=texto_hist,
                                formato="pncp_termos_json",
                                tamanho_bytes=len(raw_h),
                                min_chars_uteis=MIN_CHARS_UTEIS_GATEKEEPER,
                            )
                            doc_hist = DocumentoProcessado(
                                nome_origem=f"Termos_Contrato_{ano_id}_{seq_id}.json",
                                caminho_interno_zip=None,
                                formato_detectado="pncp_termos_json",
                                tamanho_bytes=len(raw_h),
                                sha256=hashlib.sha256(raw_h).hexdigest(),
                                aprovado_gatekeeper=aprov,
                                motivo_gatekeeper=mot,
                                chars_brutos=len(texto_hist),
                                chars_uteis_corridos=chars_u,
                                paragrafos_validos=parags,
                                eh_email_bloqueado=eh_em,
                                eh_espelho_html=eh_ht,
                                texto_util_preview=txt_corr[:400] if txt_corr else "",
                                texto_completo_limpo=txt_corr,
                                raw_bytes=raw_h if aprov else b"",
                            )
                            if doc_hist.aprovado_gatekeeper:
                                caminho_hist = pasta_destino / f"{base_nome}_contratos_{ano_id}_{seq_id}_TERMOS_HISTORICO.pdf"
                                salvo_h = _comitar_doc_pncp(
                                    doc=doc_hist,
                                    caminho_arquivo=caminho_hist,
                                    titulo_cabecalho=f"HISTÓRICO DE TERMOS ADITIVOS E RESCISÕES PNCP — CONTRATO {num_inst}",
                                    base_nome=base_nome,
                                    id_obra=id_obra,
                                    num_inst=num_inst,
                                    emp=emp,
                                    obs_extra=f"Histórico de {len(termos)} Termos PNCP | Controle: {control_id} | Fonte: {url_termos}",
                                    cache_log=cache_log,
                                    cache_hashes=cache_hashes,
                                    caminho_csv=caminho_csv,
                                )
                                if salvo_h:
                                    arquivos_validados.append(salvo_h)
            except Exception as exc_t:
                logger.debug(f"Erro ao consultar termos PNCP ({url_termos}): {exc_t}")

        # ─── NÍVEL 2: ARQUIVOS DIRETOS DA ENTIDADE (CONTRATO OU COMPRA) ──────
        url_arquivos = f"{identity['url']}/arquivos"
        try:
            resp = sess.get(url_arquivos, headers={"Accept": "application/json"}, timeout=15)
            if resp.status_code == 200 and isinstance(resp.json(), list):
                vals_c, fm, fp, fz = _processar_lista_arquivos_pncp(
                    sess=sess,
                    arquivos_api=resp.json(),
                    prefixo_nome=f"{base_nome}_{kind}_{ano_id}_{seq_id}",
                    url_origem=url_arquivos,
                    control_id=control_id,
                    base_nome=base_nome,
                    id_obra=id_obra,
                    num_inst=num_inst,
                    emp=emp,
                    pasta_destino=pasta_destino,
                    cache_log=cache_log,
                    cache_hashes=cache_hashes,
                    caminho_csv=caminho_csv,
                )
                arquivos_validados.extend(vals_c)
                tot_meta += fm
                tot_poda += fp
                tot_zips += fz
        except Exception as exc_a:
            logger.debug(f"Erro PNCP arquivos ({url_arquivos}): {exc_a}")

        # ─── NÍVEL 3: ARQUIVOS DA COMPRA VINCULADA AO CONTRATO (`numeroControlePncpCompra`) ─
        ctrl_compra = meta_contrato.get("numeroControlePncpCompra")
        comp_id = parse_control(ctrl_compra) if isinstance(ctrl_compra, str) else None
        if comp_id and comp_id["kind"] == "compras":
            url_comp_arqs = (
                f"https://pncp.gov.br/api/pncp/v1/orgaos/{comp_id['cnpj']}/"
                f"compras/{comp_id['year']}/{comp_id['sequence']}/arquivos"
            )
            try:
                rc = sess.get(url_comp_arqs, headers={"Accept": "application/json"}, timeout=15)
                if rc.status_code == 200 and isinstance(rc.json(), list):
                    vals_comp, fm, fp, fz = _processar_lista_arquivos_pncp(
                        sess=sess,
                        arquivos_api=rc.json(),
                        prefixo_nome=f"{base_nome}_compra_vinculada_{comp_id['year']}_{comp_id['sequence']}",
                        url_origem=url_comp_arqs,
                        control_id=str(ctrl_compra),
                        base_nome=base_nome,
                        id_obra=id_obra,
                        num_inst=num_inst,
                        emp=emp,
                        pasta_destino=pasta_destino,
                        cache_log=cache_log,
                        cache_hashes=cache_hashes,
                        caminho_csv=caminho_csv,
                    )
                    arquivos_validados.extend(vals_comp)
                    tot_meta += fm
                    tot_poda += fp
                    tot_zips += fz
            except Exception as exc_comp:
                logger.debug(f"Erro PNCP compra vinculada ({url_comp_arqs}): {exc_comp}")

        if tot_meta + tot_poda + tot_zips > 0 or arquivos_validados:
            logger.info(
                f"    [CURADORIA PNCP] {base_nome} {id_obra} ({control_id}): "
                f"+{len(arquivos_validados)} aprovados | {tot_zips} ZIPs abertos in-memory | "
                f"{tot_meta} API bloqueados | {tot_poda} Gatekeeper podados"
            )

    except Exception as exc:
        logger.debug(f"Erro PNCP {base_nome} ({id_obra}): {exc}")

    return arquivos_validados
