"""Modulo de particionamento estratificado por grupos de obra (id_tcu) e isolamento temporal."""
import hashlib
from typing import Dict, Any, Set
import numpy as np
import pandas as pd


def _hash_seed_group(id_tcu: str, seed: int) -> int:
    """Calcula hash deterministico de id_tcu + seed para ordenacao pseudo-aleatoria estavel."""
    h = hashlib.sha256(f"{seed}_{id_tcu}".encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def audit_leakage(df: pd.DataFrame) -> Dict[str, Any]:
    """Audita vazamento de identidade de obras (id_tcu) entre as particoes geradas."""
    if "particao" not in df.columns or "id_tcu" not in df.columns:
        raise ValueError("DataFrame deve conter as colunas 'particao' e 'id_tcu'")
    
    dev_mask = df["particao"] == "treino_dev"
    test_mask = df["particao"] == "teste_retido"
    
    dev_obras: Set[str] = set(df.loc[dev_mask, "id_tcu"].dropna())
    test_obras: Set[str] = set(df.loc[test_mask, "id_tcu"].dropna())
    
    intersecao = dev_obras & test_obras
    
    # Verifica vazamento de 2026 no treino/teste se existir particao isolado_2026
    leak_2026 = 0
    if "isolado_2026" in df["particao"].values:
        obras_2026: Set[str] = set(df.loc[df["particao"] == "isolado_2026", "id_tcu"].dropna())
        # Observacoes de 2026 nao devem ter id_fato nos conjuntos de treino/teste de 2025
        # (Nota: id_tcu fisico pode ter continuidade historica, mas o registro de 2026 nao pode estar no treino)
        if "ano" in df.columns:
            treino_anos = df.loc[dev_mask | test_mask, "ano"].unique()
            if 2026 in treino_anos:
                leak_2026 = int((df.loc[dev_mask | test_mask, "ano"] == 2026).sum())
    
    vazamento = len(intersecao) > 0 or leak_2026 > 0
    
    return {
        "vazamento_detectado": vazamento,
        "intersecao_obras": len(intersecao),
        "obras_vazadas": sorted(list(intersecao)),
        "vazamento_linhas_2026": leak_2026,
        "total_treino": int(dev_mask.sum()),
        "total_teste": int(test_mask.sum()),
        "obras_unicas_treino": len(dev_obras),
        "obras_unicas_teste": len(test_obras),
    }


def partition_by_work_identity(
    df: pd.DataFrame,
    seed: int = 42,
    test_ratio: float = 0.20,
) -> pd.DataFrame:
    """Particiona observacoes por grupo de identidade de obra (id_tcu) de forma estratificada.
    
    Regras da Constituicao do Projeto:
    1. Observacoes de 2026 vao para particao 'isolado_2026'.
    2. Observacoes de 2025 com label_risco nulo vao para particao 'pendentes_2025'.
    3. Observacoes de 2025 rotuladas (classes 0, 1, 2, 3) sao particionadas em 'treino_dev' (80%)
       e 'teste_retido' (20%) agrupando estritamente por id_tcu (zero vazamento de obra).
    """
    df_out = df.copy()
    df_out["particao"] = "pendente_atribuicao"
    
    # 1. Isolamento de 2026
    if "ano" in df_out.columns:
        mask_2026 = df_out["ano"] == 2026
        df_out.loc[mask_2026, "particao"] = "isolado_2026"
    else:
        mask_2026 = pd.Series(False, index=df_out.index)
        
    # 2. Casos pendentes de 2025
    if "label_risco" in df_out.columns:
        mask_pendente = (~mask_2026) & (df_out["label_risco"].isna())
        df_out.loc[mask_pendente, "particao"] = "pendentes_2025"
        
        mask_rotulado = (~mask_2026) & (df_out["label_risco"].notna())
    else:
        mask_rotulado = ~mask_2026
        
    df_rot = df_out.loc[mask_rotulado]
    if len(df_rot) == 0:
        return df_out
        
    # Agrupa obras unicas da populacao rotulada
    # Para cada obra unica, define classe representativa (maximo de label_risco em caso de divergencia)
    obras_info = (
        df_rot.groupby("id_tcu")
        .agg(
            classe_representativa=("label_risco", lambda s: int(s.max())),
            num_linhas=("id_fato" if "id_fato" in df_rot.columns else "id_tcu", "count")
        )
        .reset_index()
    )
    
    # Adiciona valor de hash pseudo-aleatorio baseado na semente fixa
    obras_info["sort_key"] = obras_info["id_tcu"].apply(lambda id_: _hash_seed_group(id_, seed))
    
    dev_obras: Set[str] = set()
    test_obras: Set[str] = set()
    
    # Estratifica por classe representativa (0, 1, 2, 3)
    classes_unicas = sorted(obras_info["classe_representativa"].unique())
    for c in classes_unicas:
        sub_obras = obras_info[obras_info["classe_representativa"] == c].sort_values("sort_key")
        n_c = len(sub_obras)
        
        if n_c == 1:
            # Caso extremo de classe com 1 unica obra: fica em desenvolvimento para permitir treino
            dev_obras.add(sub_obras.iloc[0]["id_tcu"])
        else:
            n_test = max(1, int(round(n_c * test_ratio)))
            # Garante que teste nao pegue 100% da classe
            if n_test >= n_c:
                n_test = n_c - 1
                
            test_ids = set(sub_obras.iloc[:n_test]["id_tcu"])
            dev_ids = set(sub_obras.iloc[n_test:]["id_tcu"])
            
            test_obras.update(test_ids)
            dev_obras.update(dev_ids)
            
    # Atribui as particoes
    mask_in_test = df_out["id_tcu"].isin(test_obras) & mask_rotulado
    mask_in_dev = df_out["id_tcu"].isin(dev_obras) & mask_rotulado
    
    df_out.loc[mask_in_test, "particao"] = "teste_retido"
    df_out.loc[mask_in_dev, "particao"] = "treino_dev"
    
    # Executa auditoria interna de vazamento
    audit = audit_leakage(df_out)
    if audit["vazamento_detectado"]:
        raise RuntimeError(f"Vazamento critico de dados detectado na particao: {audit}")
        
    return df_out
