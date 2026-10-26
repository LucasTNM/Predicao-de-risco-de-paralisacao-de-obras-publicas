import pandas as pd
from pathlib import Path

drive_root = Path(r"G:\Meu Drive\TCC_DOCUMENTOS")
for ano in ["2022", "2023", "2024", "2025", "2026"]:
    log_csv = drive_root / f"{ano}_Dados_brutos" / "log_coleta.csv"
    planilha = Path(f"data_{ano}.xlsx")
    if not log_csv.exists():
        continue
    df_log = pd.read_csv(log_csv, dtype=str, on_bad_lines="skip")
    df_plan = pd.read_excel(planilha, dtype=str)
    df_plan.columns = [c.strip().lower() for c in df_plan.columns]
    col_sit = [c for c in df_plan.columns if "situa" in c][0]
    par_ids = set(
        df_plan[
            df_plan[col_sit]
            .astype(str)
            .str.contains(r"paralis|inacab|rescind|cancel|suspens", case=False, na=False)
        ]["id"].str.strip()
    )
    df_log["is_new"] = df_log["timestamp"].astype(str).str.startswith("2026-10-")
    df_val = df_log[df_log["status_validacao"].isin(["VALIDADO", "VALIDADO_COM_RESSALVAS"])].copy()
    fichas = ["_FichaTecnica_Saude.pdf", "_FichaTecnica_FNDE.pdf", "_Relatorio_Tecnico.pdf"]
    df_val = df_val[~df_val["nome_arquivo"].str.contains("|".join(fichas), na=False, case=False)]
    df_val["is_par"] = df_val["id_obra"].str.strip().isin(par_ids)
    df_val["is_reuso"] = df_val["observacoes"].astype(str).str.contains("Reuso Cross-Ano", na=False)

    print(f"=== ANO {ano} (Paralisadas na planilha: {len(par_ids)}) ===")
    print(
        f"  Total validados no CSV (sem ficha sintetica): {len(df_val):,} | Obras unicas: {df_val['id_obra'].nunique():,}"
    )
    print(
        f"  Desses, obras PARALISADAS na planilha {ano}: {df_val[df_val['is_par']]['id_obra'].nunique():,} | Docs: {len(df_val[df_val['is_par']]):,}"
    )
    novos = df_val[df_val["is_new"]]
    print(
        f"  Adicionados nesta execucao (2026-10-*): {len(novos):,} docs | Obras: {novos['id_obra'].nunique():,}"
    )
    diretos = novos[~novos["is_reuso"]]
    reusos = novos[novos["is_reuso"]]
    print(
        f"    -> Download Direto da Web/API: {len(diretos):,} docs em {diretos['id_obra'].nunique():,} obras"
    )
    print(
        f"    -> Reuso Cross-Ano O(1):       {len(reusos):,} docs em {reusos['id_obra'].nunique():,} obras"
    )
    for b, grp in novos.groupby("base_de_dados"):
        d_b = grp[~grp["is_reuso"]]
        r_b = grp[grp["is_reuso"]]
        print(
            f"      [{b}] total_obras={grp['id_obra'].nunique()} "
            f"(direto={d_b['id_obra'].nunique()} obras / {len(d_b)} docs | "
            f"reuso={r_b['id_obra'].nunique()} obras / {len(r_b)} docs)"
        )
    print()
