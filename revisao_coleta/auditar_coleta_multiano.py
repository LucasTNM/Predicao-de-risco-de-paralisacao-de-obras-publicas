import pandas as pd
from pathlib import Path

anos = ["2022", "2023", "2024", "2025", "2026"]
drive_root = Path(r"G:\Meu Drive\TCC_DOCUMENTOS")

print("=== AUDITORIA COMPLETA DE COLETA MULTIANO (2022-2026) ===\n")

tot_obras_geral = set()
tot_docs_geral = 0
resumo_tabela = []

for ano in anos:
    pasta_ano = drive_root / f"{ano}_Dados_brutos"
    log_csv = pasta_ano / "log_coleta.csv"
    if not log_csv.exists():
        print(f"Ano {ano}: log_coleta.csv NÃO encontrado em {log_csv}")
        continue
    df = pd.read_csv(log_csv, sep=",", dtype=str, on_bad_lines="skip")
    # Documentos validados
    df_val = df[df["status_validacao"].isin(["VALIDADO", "VALIDADO_COM_RESSALVAS"])].copy()
    
    # Filtra fichas sintéticas legadas caso ainda existam no log
    fichas_legadas = ["_FichaTecnica_Saude.pdf", "_FichaTecnica_FNDE.pdf", "_Relatorio_Tecnico.pdf"]
    df_val = df_val[~df_val["nome_arquivo"].str.contains("|".join(fichas_legadas), na=False, case=False)]
    
    obras_unicas = df_val.groupby(["base_de_dados", "id_obra"]).size()
    total_docs = len(df_val)
    total_obras = len(obras_unicas)
    tot_docs_geral += total_docs
    for b, i in obras_unicas.index:
        tot_obras_geral.add((str(b).lower(), i))

    print(f"--- ANO BASE {ano} ---")
    print(f"Total de registros no log: {len(df):,}")
    print(f"Total de documentos autênticos validados: {total_docs:,}")
    print(f"Total de obras únicas com documentos: {total_obras:,}")
    print("Distribuição por Base:")
    por_base = df_val.groupby("base_de_dados").agg(
        obras=("id_obra", "nunique"),
        documentos=("id_obra", "count")
    )
    for b_nome, r in por_base.iterrows():
        print(f"  - {str(b_nome).upper():<12}: {r['obras']:>5} obras | {r['documentos']:>6} docs")
        resumo_tabela.append({
            "ano": ano,
            "base": str(b_nome).upper(),
            "obras": r["obras"],
            "documentos": r["documentos"]
        })
    print()

print("=" * 60)
print("TOTAL CONSOLIDADO 2022-2026:")
print(f"Total de Documentos Autênticos Coletados: {tot_docs_geral:,}")
print(f"Total de Obras Únicas com Documentos Autênticos: {len(tot_obras_geral):,}")
print("=" * 60)
