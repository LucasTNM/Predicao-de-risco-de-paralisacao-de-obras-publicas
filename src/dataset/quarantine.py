"""Modulo de quarentena documental.

Carrega e gerencia a lista oficial de documentos invalidados da Feature 012
(36 vinculos de documentos DNIT comprovadamente incompativeis com os contratos).
"""
from pathlib import Path
import json
from typing import Set, Dict, Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUARANTINE_FILE = ROOT / "logs" / "piloto_recuperacao" / "quarentena_vinculos.json"

# IDs canonicos oficiais dos 36 documentos sob quarentena
CANONICAL_QUARANTINED_DOC_IDS = {
    8, 9, 204, 209, 213, 214, 229, 236, 245, 278, 293, 321, 322, 323, 324, 325,
    332, 333, 334, 335, 336, 337, 338, 440, 514, 518, 541, 572, 591, 602, 603,
    604, 605, 626, 627, 628
}


def load_quarantine_data(path: Path | None = None) -> list[dict]:
    """Carrega o arquivo json de quarentena de vinculos."""
    file_path = path or DEFAULT_QUARANTINE_FILE
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_quarantined_document_ids(path: Path | None = None) -> Set[int]:
    """Retorna conjunto de IDs de documentos sob quarentena."""
    data = load_quarantine_data(path)
    if not data:
        return set(CANONICAL_QUARANTINED_DOC_IDS)
    
    ids: Set[int] = set()
    for item in data:
        for doc in item.get("documentos", []):
            if "id_documento" in doc:
                ids.add(int(doc["id_documento"]))
    
    return ids or set(CANONICAL_QUARANTINED_DOC_IDS)


def get_quarantined_hashes(path: Path | None = None) -> Set[str]:
    """Retorna conjunto de hashes SHA-256 canonicos sob quarentena."""
    data = load_quarantine_data(path)
    hashes: Set[str] = set()
    for item in data:
        for doc in item.get("documentos", []):
            h = doc.get("sha256_canonico") or doc.get("sha256_esperado") or doc.get("sha256_lido")
            if h:
                hashes.add(str(h).lower())
    return hashes


def is_document_quarantined(id_documento: int, sha256: str | None = None, path: Path | None = None) -> bool:
    """Verifica se um documento esta sob quarentena por ID ou hash."""
    quarantined_ids = get_quarantined_document_ids(path)
    if id_documento in quarantined_ids:
        return True
    if sha256:
        quarantined_hashes = get_quarantined_hashes(path)
        if sha256.lower() in quarantined_hashes:
            return True
    return False


def get_quarantine_summary(path: Path | None = None) -> Dict[str, Any]:
    """Retorna metadados resumidos da quarentena para manifestos."""
    q_ids = get_quarantined_document_ids(path)
    data = load_quarantine_data(path)
    obras_afetadas = len(data) if data else 22
    return {
        "documentos_excluidos": len(q_ids),
        "obras_afetadas": obras_afetadas,
        "motivo": "Incompatibilidade de objeto comprovada na Feature 012 (servicos/locacao associados a rodovias)",
        "documentos_ids": sorted(list(q_ids)),
    }
