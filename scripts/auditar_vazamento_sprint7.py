# -*- coding: utf-8 -*-
"""
scripts/auditar_vazamento_sprint7.py
===================================
Script auditável em modo estritamente SOMENTE LEITURA para documentar o grau de
vazamento do alvo (Target Leakage) nos fragmentos textuais (fichas sintéticas)
e nos metadados/contadores de documentos para as observações rotuladas de 2025.

Conforme a Constituição do TCC (Art. I e IV) e Feature 018 do SpecKit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.connection import connect


def run_leakage_audit() -> Dict[str, Any]:
    """Executa consultas analíticas somente leitura e retorna diagnóstico completo."""
    conn = connect()
    conn.read_only = True

    try:
        # 1. Distribuição documental por classe de risco em 2025
        q_dist = """
        WITH docs AS (
            SELECT
                f.id_fato,
                f.label_risco,
                bool_or(d.origem_documento = 'ficha_sintetica') AS tem_ficha,
                bool_or(d.origem_documento <> 'ficha_sintetica') AS tem_outro
            FROM tcc.fato_risco f
            LEFT JOIN tcc.ponte_documento_embedding p ON p.id_fato = f.id_fato
            LEFT JOIN tcc.dim_documento d ON d.id_documento = p.id_documento
            WHERE f.ano_base = 2025 AND f.label_risco IS NOT NULL
            GROUP BY f.id_fato, f.label_risco
        )
        SELECT
            label_risco,
            count(*)::int AS total,
            count(*) FILTER (WHERE tem_ficha IS NULL)::int AS sem_docs,
            count(*) FILTER (WHERE tem_ficha AND NOT coalesce(tem_outro, false))::int AS so_ficha,
            count(*) FILTER (WHERE tem_ficha AND tem_outro)::int AS ficha_e_outro,
            count(*) FILTER (WHERE NOT tem_ficha)::int AS so_outros
        FROM docs
        GROUP BY label_risco
        ORDER BY label_risco;
        """
        rows_dist = conn.execute(q_dist).fetchall()
        distribuicao_classes: List[Dict[str, int]] = []
        for r in rows_dist:
            distribuicao_classes.append({
                "label_risco": r[0],
                "total": r[1],
                "sem_docs": r[2],
                "so_ficha": r[3],
                "ficha_e_outro": r[4],
                "so_outros": r[5],
            })

        # 2. Presença de termos reveladores do alvo nos chunks de fichas sintéticas
        q_termos = """
        WITH f AS (
            SELECT
                fr.id_fato,
                fr.label_risco,
                bool_or(e.conteudo_chunk ILIKE '%%paralisad%%') AS paralisad,
                bool_or(e.conteudo_chunk ILIKE '%%em execu%%') AS em_exec,
                bool_or(e.conteudo_chunk ILIKE '%%conclu%%') AS conclu
            FROM tcc.fato_risco fr
            JOIN tcc.ponte_documento_embedding p ON p.id_fato = fr.id_fato
            JOIN tcc.dim_documento d ON d.id_documento = p.id_documento
            JOIN tcc.dim_embedding e ON e.id_embedding = p.id_embedding
            WHERE fr.ano_base = 2025 AND fr.label_risco IS NOT NULL
              AND d.origem_documento = 'ficha_sintetica'
            GROUP BY fr.id_fato, fr.label_risco
        )
        SELECT
            label_risco,
            count(*)::int AS obras_com_ficha,
            count(*) FILTER (WHERE paralisad)::int AS com_paralisad,
            count(*) FILTER (WHERE em_exec)::int AS com_em_exec,
            count(*) FILTER (WHERE conclu)::int AS com_conclu
        FROM f
        GROUP BY label_risco
        ORDER BY label_risco;
        """
        rows_termos = conn.execute(q_termos).fetchall()
        termos_por_classe: List[Dict[str, int]] = []
        for r in rows_termos:
            termos_por_classe.append({
                "label_risco": r[0],
                "obras_com_ficha": r[1],
                "com_paralisad": r[2],
                "com_em_exec": r[3],
                "com_conclu": r[4],
            })

        # 3. Chunks totais de fichas sintéticas de 2025
        q_chunks = """
        SELECT
            count(DISTINCT e.id_embedding)::int AS chunks_ficha,
            count(DISTINCT e.id_embedding) FILTER (WHERE e.conteudo_chunk ILIKE '%%paralisad%%')::int AS com_paralisad,
            count(DISTINCT e.id_embedding) FILTER (WHERE e.conteudo_chunk ILIKE '%%causa%%')::int AS com_causa
        FROM tcc.dim_embedding e
        JOIN tcc.ponte_documento_embedding p USING (id_embedding)
        JOIN tcc.dim_documento d USING (id_documento)
        WHERE d.origem_documento = 'ficha_sintetica' AND d.ano_base = 2025;
        """
        r_chunks = conn.execute(q_chunks).fetchone()
        chunks_resumo = {
            "total_chunks_fichas": r_chunks[0],
            "chunks_com_paralisad": r_chunks[1],
            "chunks_com_causa": r_chunks[2],
        }

        # 4. Distribuição de bases que geraram fichas sintéticas
        q_bases = """
        SELECT
            d.origem_documento,
            d.base_origem,
            count(DISTINCT fr.id_fato)::int AS obras_rotuladas
        FROM tcc.fato_risco fr
        JOIN tcc.ponte_documento_embedding p ON p.id_fato = fr.id_fato
        JOIN tcc.dim_documento d ON d.id_documento = p.id_documento
        WHERE fr.ano_base = 2025 AND fr.label_risco IS NOT NULL
        GROUP BY d.origem_documento, d.base_origem
        ORDER BY d.origem_documento, d.base_origem;
        """
        rows_bases = conn.execute(q_bases).fetchall()
        bases_origem = [
            {"origem": r[0], "base": r[1], "obras": r[2]} for r in rows_bases
        ]

        return {
            "distribuicao_classes": distribuicao_classes,
            "termos_por_classe": termos_por_classe,
            "chunks_resumo": chunks_resumo,
            "bases_origem": bases_origem,
        }
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoria de vazamento de alvo nos textos de 2025")
    parser.add_argument("--json", action="store_true", help="Imprime resultado em formato JSON")
    args = parser.parse_args()

    data = run_leakage_audit()

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print("================================================================================")
    print("AUDITORIA DE VAZAMENTO DE ALVO (TARGET LEAKAGE) - ANO-BASE 2025")
    print("================================================================================")
    print("\n1. Distribuicao Documental por Classe de Risco (18.154 rotuladas):")
    print(f"{'Classe':<8} | {'Total':<7} | {'Sem Docs':<9} | {'So Ficha':<9} | {'Ficha+Outro':<11} | {'So Outros':<9}")
    print("-" * 65)
    for c in data["distribuicao_classes"]:
        print(f"{c['label_risco']:<8} | {c['total']:<7} | {c['sem_docs']:<9} | {c['so_ficha']:<9} | {c['ficha_e_outro']:<11} | {c['so_outros']:<9}")

    print("\n2. Presenca de Termos Reveladores de Alvo nas Fichas Sinteticas:")
    print(f"{'Classe':<8} | {'Obras c/ Ficha':<14} | {'Contem Paralisada':<18} | {'Contem Em Execucao':<18} | {'Contem Concluida':<16}")
    print("-" * 85)
    for t in data["termos_por_classe"]:
        print(f"{t['label_risco']:<8} | {t['obras_com_ficha']:<14} | {t['com_paralisad']:<18} | {t['com_em_exec']:<18} | {t['com_conclu']:<16}")

    print("\n3. Resumo de Chunks de Fichas Sinteticas:")
    cr = data["chunks_resumo"]
    print(f"Total de Chunks: {cr['total_chunks_fichas']} | Com 'paralisad': {cr['chunks_com_paralisad']} | Com 'causa': {cr['chunks_com_causa']}")

    print("\n4. Provedores Documentais (Bases de Origem):")
    for b in data["bases_origem"]:
        print(f" - Origem: {b['origem']:<16} | Base: {b['base']:<12} | Obras: {b['obras']}")
    print("================================================================================")


if __name__ == "__main__":
    main()
