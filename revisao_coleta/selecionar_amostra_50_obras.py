# -*- coding: utf-8 -*-
"""
revisao_coleta/selecionar_amostra_50_obras.py
=============================================
FASE 3: Seleção determinística (semente 42) da amostra de 50 obras paralisadas de 2025
que ficaram sem documento autêntico na Sprint 7.

Distribuição estratificada prioritária (Total = 50 obras paralisadas de 2025):
- 15 obras CAIXA / Transferegov (com número de convênio de 6 dígitos e diferentes causas)
- 5 obras FUNASA / Transferegov (convênios / termos de compromisso)
- 10 obras DNIT (contratos de engenharia rodoviária 2021-2024 para sondagem profunda no PNCP Contratos/Termos/Aditivos/Rescisões e Obrasgov)
- 10 obras SIMEC (Obras 2.0 / FNDE com ID SIMEC para sondagem de Restrições, Vistorias e Anexos)
- 10 obras SISMOB (Ministério da Saúde com CNPJ + Proposta para sondagem na API pública SISMOB Cidadão)
"""

from __future__ import annotations

import json
from pathlib import Path
import random
import re
import sys
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils import normalizar_coluna


def carregar_obras_com_doc_autentico_sprint7() -> set[str]:
    """Retorna os IDs das 12 obras paralisadas que já tinham documento autêntico na Sprint 7."""
    ids_com_doc: set[str] = set()
    for fname in ("evidencias_rag_dev.jsonl", "evidencias_rag_teste.jsonl"):
        fpath = ROOT_DIR / "dados_processados/sprint7" / fname
        if fpath.exists():
            for line in fpath.read_text(encoding="utf-8").splitlines():
                obj = json.loads(line)
                if not obj.get("sem_evidencia_textual"):
                    ids_com_doc.add(str(obj.get("id_tcu", "")).strip())
    return ids_com_doc


def selecionar_amostra_50_obras(seed: int = 42) -> list[dict[str, Any]]:
    df = pd.read_excel(ROOT_DIR / "data_2025.xlsx")
    df.columns = [normalizar_coluna(c) for c in df.columns]

    ids_com_doc_sprint7 = carregar_obras_com_doc_autentico_sprint7()

    # Filtra apenas obras paralisadas de 2025 que NÃO tinham documento autêntico na Sprint 7
    paralisadas = df[
        df["situacao"].astype(str).str.lower().str.contains("paralisad", na=False)
        & (~df["id"].astype(str).str.strip().isin(ids_com_doc_sprint7))
    ].copy()

    rng = random.Random(seed)
    amostra: list[dict[str, Any]] = []

    def _row_to_dict(row: pd.Series, estrato: str) -> dict[str, Any]:
        return {
            "id": str(row.get("id", "")).strip(),
            "base_de_dados": str(row.get("base de dados", "")).strip().upper(),
            "estrato_sondagem": estrato,
            "num_instrumento": "" if pd.isna(row.get("num. instrumento")) else str(row.get("num. instrumento")).strip(),
            "empreendimento": "" if pd.isna(row.get("empreendimento")) else str(row.get("empreendimento")).strip(),
            "local": "" if pd.isna(row.get("local")) else str(row.get("local")).strip(),
            "situacao": "" if pd.isna(row.get("situacao")) else str(row.get("situacao")).strip(),
            "situacao_origem": "" if pd.isna(row.get("situacao origem")) else str(row.get("situacao origem")).strip(),
            "causa_paralisacao_tabular": (
                "" if pd.isna(row.get("causa da paralisacao")) else str(row.get("causa da paralisacao")).strip()
            ),
            "exec_fisica": float(row.get("exec. fisica", 0) or 0),
            "valor_investimento": float(row.get("valor investimento", 0) or 0),
        }

    # 1. CAIXA (15 obras paralisadas com número de convênio SICONV/Transferegov válido)
    caixa_df = paralisadas[
        (paralisadas["base de dados"].astype(str).str.upper() == "CAIXA")
        & (paralisadas["num. instrumento"].notna())
    ].sort_values("id")
    # Prioriza convênios mais recentes (numeração >= 800000) e intermediários para ter diversidade
    caixa_recentes = caixa_df[
        caixa_df["num. instrumento"].astype(str).str.extract(r"(\d+)", expand=False).fillna("0").astype(int) >= 800000
    ]
    caixa_antigos = caixa_df[
        caixa_df["num. instrumento"].astype(str).str.extract(r"(\d+)", expand=False).fillna("0").astype(int) < 800000
    ]
    escolhidos_caixa = (
        rng.sample(list(caixa_recentes.iterrows()), min(10, len(caixa_recentes)))
        + rng.sample(list(caixa_antigos.iterrows()), min(5, len(caixa_antigos)))
    )
    for _, r in escolhidos_caixa:
        amostra.append(_row_to_dict(r, "TRANSFEREGOV_CAIXA"))

    # 2. FUNASA (5 obras paralisadas com convênio numérico ou TC/PAC)
    funasa_df = paralisadas[
        (paralisadas["base de dados"].astype(str).str.upper() == "FUNASA")
        & (paralisadas["num. instrumento"].notna())
    ].sort_values("id")
    funasa_num = funasa_df[funasa_df["num. instrumento"].astype(str).str.match(r"^\d{6}$")]
    funasa_tc = funasa_df[~funasa_df["num. instrumento"].astype(str).str.match(r"^\d{6}$")]
    escolhidos_funasa = (
        rng.sample(list(funasa_num.iterrows()), min(3, len(funasa_num)))
        + rng.sample(list(funasa_tc.iterrows()), min(2, len(funasa_tc)))
    )
    for _, r in escolhidos_funasa:
        amostra.append(_row_to_dict(r, "TRANSFEREGOV_FUNASA"))

    # 3. DNIT (10 obras paralisadas com contrato registrado no PNCP 2023-2024 para testar PNCP Contratos/Termos/Aditivos/Rescisões)
    ids_dnit_pncp = {
        "DNIT-11746", "DNIT-11214", "DNIT-11675", "DNIT-11570", "DNIT-11555",
        "DNIT-11314", "DNIT-11423", "DNIT-11368", "DNIT-11654", "DNIT-11609", "DNIT-11538"
    }
    dnit_df = paralisadas[
        (paralisadas["base de dados"].astype(str).str.upper() == "DNIT")
        & (paralisadas["id"].astype(str).str.strip().isin(ids_dnit_pncp))
    ].sort_values("id")
    escolhidos_dnit = rng.sample(list(dnit_df.iterrows()), min(10, len(dnit_df)))
    for _, r in escolhidos_dnit:
        amostra.append(_row_to_dict(r, "PNCP_DNIT"))

    # 4. SIMEC (10 obras paralisadas do Obras 2.0 / FNDE)
    simec_df = paralisadas[
        paralisadas["base de dados"].astype(str).str.upper() == "SIMEC"
    ].sort_values("id")
    escolhidos_simec = rng.sample(list(simec_df.iterrows()), min(10, len(simec_df)))
    for _, r in escolhidos_simec:
        amostra.append(_row_to_dict(r, "SIMEC_OBRAS2"))

    # 5. SISMOB (10 obras paralisadas do Ministério da Saúde)
    sismob_df = paralisadas[
        paralisadas["base de dados"].astype(str).str.upper() == "SISMOB"
    ].sort_values("id")
    escolhidos_sismob = rng.sample(list(sismob_df.iterrows()), min(10, len(sismob_df)))
    for _, r in escolhidos_sismob:
        amostra.append(_row_to_dict(r, "SISMOB_SAUDE"))

    assert len(amostra) == 50, f"Esperado 50 obras, obtido {len(amostra)}"

    out_path = ROOT_DIR / "revisao_coleta/resultados/amostra_50_obras_paralisadas_2025.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "seed": seed,
                "total_obras_amostra": len(amostra),
                "distribuicao_por_estrato": {
                    "TRANSFEREGOV_CAIXA": 15,
                    "TRANSFEREGOV_FUNASA": 5,
                    "PNCP_DNIT": 10,
                    "SIMEC_OBRAS2": 10,
                    "SISMOB_SAUDE": 10,
                },
                "obras": amostra,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[FASE 3] Amostra de {len(amostra)} obras paralisadas de 2025 salva em: {out_path}")
    return amostra


if __name__ == "__main__":
    selecionar_amostra_50_obras()
