# -*- coding: utf-8 -*-
"""
revisao_coleta/fase3_sondagem_50_obras.py
=========================================
FASE 3: Runner do Benchmark Real nas 50 Obras Paralisadas de 2025.

Executa os conectores profundos de `revisao_coleta/sondagem_endpoints.py`
e o motor multiformato (`revisao_coleta/motor_multiformato.py`) sobre as
50 obras paralisadas da amostra `amostra_50_obras_paralisadas_2025.json`.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from revisao_coleta.sondagem_endpoints import (
    PNCPContractsIndex,
    TransferegovProbeSession,
    carregar_contratos_siconv_cipi,
    carregar_crosswalk_siconv_cipi,
    sondar_obra_pncp_profundo,
    sondar_obra_simec_obras2,
    sondar_obra_sismob_api,
    sondar_obra_transferegov_profundo,
)


def executar_benchmark_50_obras() -> dict[str, Any]:
    t0 = time.time()
    amostra_path = ROOT_DIR / "revisao_coleta/resultados/amostra_50_obras_paralisadas_2025.json"
    dados_amostra = json.loads(amostra_path.read_text(encoding="utf-8"))
    obras = dados_amostra["obras"]

    print(f"[FASE 3] Carregando crosswalks locais SICONV/CIPI e índice de contratos PNCP...")
    mapa_cipi = carregar_crosswalk_siconv_cipi()
    mapa_contratos_cipi = carregar_contratos_siconv_cipi()

    indice_pncp = PNCPContractsIndex()
    indice_pncp.carregar_anos([2023, 2024])
    print(f"  -> Contratos DNIT indexados no PNCP (2023-2024): {indice_pncp.total_contratos_indexados}")

    print(f"[FASE 3] Autenticando sessão Transferegov via Selenium Manager...")
    tg_session_mgr = TransferegovProbeSession()
    print(f"  -> Transferegov autenticado: {tg_session_mgr.autenticado}")

    cache_municipios_ibge: dict[str, str] = {}
    resultados_obras: list[dict[str, Any]] = []

    for idx, obra in enumerate(obras, start=1):
        id_obra = obra["id"]
        estrato = obra["estrato_sondagem"]
        t_obra = time.time()

        if estrato in ("TRANSFEREGOV_CAIXA", "TRANSFEREGOV_FUNASA"):
            res = sondar_obra_transferegov_profundo(
                obra=obra,
                sess=tg_session_mgr.session,
                mapa_cipi=mapa_cipi,
                mapa_contratos_cipi=mapa_contratos_cipi,
            )
        elif estrato == "PNCP_DNIT":
            res = sondar_obra_pncp_profundo(
                obra=obra,
                indice_contratos=indice_pncp,
            )
        elif estrato == "SIMEC_OBRAS2":
            res = sondar_obra_simec_obras2(obra=obra)
        elif estrato == "SISMOB_SAUDE":
            res = sondar_obra_sismob_api(obra=obra, cache_municipios_ibge=cache_municipios_ibge)
        else:
            res = {"id_obra": id_obra, "erro": f"Estrato desconhecido: {estrato}"}

        res["estrato_sondagem"] = estrato
        res["duracao_segundos"] = round(time.time() - t_obra, 2)
        aprovados = res.get("documentos_aprovados_gatekeeper") or []
        print(
            f"  [{idx:02d}/50] {id_obra:<26} ({estrato:<20}) -> "
            f"{len(aprovados)} docs aprovados (>=800 chars) em {res['duracao_segundos']:.1f}s"
        )
        resultados_obras.append(res)

    # Consolidação de métricas por fonte/estrato
    resumo_por_estrato: dict[str, dict[str, Any]] = {}
    for estrato in ("TRANSFEREGOV_CAIXA", "TRANSFEREGOV_FUNASA", "PNCP_DNIT", "SIMEC_OBRAS2", "SISMOB_SAUDE"):
        sub = [r for r in resultados_obras if r.get("estrato_sondagem") == estrato]
        total_obras_est = len(sub)
        obras_com_doc_novo = sum(1 for r in sub if len(r.get("documentos_aprovados_gatekeeper") or []) > 0)
        todos_docs_aprovados = [
            d for r in sub for d in (r.get("documentos_aprovados_gatekeeper") or [])
        ]
        chars_lista = [d.get("chars_uteis_corridos", 0) for d in todos_docs_aprovados if d.get("chars_uteis_corridos", 0) > 0]
        densidade_media = round(statistics.mean(chars_lista), 1) if chars_lista else 0.0
        formatos_cnt = Counter(d.get("formato_detectado", "") for d in todos_docs_aprovados)
        endpoints_cnt = Counter(d.get("endpoint_origem", "") for d in todos_docs_aprovados)

        resumo_por_estrato[estrato] = {
            "total_obras_sondadas": total_obras_est,
            "obras_com_documento_autentico_antes_na_amostra": 0,
            "obras_com_documento_denso_aprovado_agora": obras_com_doc_novo,
            "ganho_cobertura_percentual_amostra": round((obras_com_doc_novo / max(total_obras_est, 1)) * 100.0, 2),
            "total_documentos_densos_aprovados_gatekeeper": len(todos_docs_aprovados),
            "densidade_media_chars_uteis": densidade_media,
            "por_formato": dict(formatos_cnt),
            "por_endpoint": dict(endpoints_cnt),
        }

    total_obras_global = len(resultados_obras)
    total_obras_recuperadas_global = sum(
        1 for r in resultados_obras if len(r.get("documentos_aprovados_gatekeeper") or []) > 0
    )
    todos_docs_global = [
        d for r in resultados_obras for d in (r.get("documentos_aprovados_gatekeeper") or [])
    ]
    densidade_media_global = (
        round(statistics.mean([d["chars_uteis_corridos"] for d in todos_docs_global]), 1)
        if todos_docs_global
        else 0.0
    )

    consolidado = {
        "feature": "021-revisao-expansao-coleta",
        "fase": "Fase 3 - Sondagem Profunda de Novos Endpoints em 50 Obras Paralisadas de 2025",
        "tempo_total_segundos": round(time.time() - t0, 2),
        "total_obras_amostra": total_obras_global,
        "total_obras_recuperadas_com_docs_densos": total_obras_recuperadas_global,
        "ganho_cobertura_global_amostra_pct": round((total_obras_recuperadas_global / total_obras_global) * 100.0, 2),
        "total_novos_documentos_aprovados_gatekeeper": len(todos_docs_global),
        "densidade_media_global_chars_uteis": densidade_media_global,
        "resumo_por_estrato": resumo_por_estrato,
        "resultados_por_obra": resultados_obras,
    }

    out_path = ROOT_DIR / "revisao_coleta/resultados/fase3_benchmark_50_obras.json"
    out_path.write_text(json.dumps(consolidado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[FASE 3 CONCLUÍDA] Relatório salvo em: {out_path}")
    print(json.dumps(resumo_por_estrato, indent=2, ensure_ascii=False))
    return consolidado


if __name__ == "__main__":
    executar_benchmark_50_obras()
