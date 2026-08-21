"""
Inspeciona um PDF e produz um JSON compacto para classificação por agente.

Responsabilidades:
- validar estrutura básica do PDF;
- obter metadados;
- extrair texto de páginas representativas;
- contar palavras-chave;
- indicar sinais de documento federal/obra pública.

Não classifica definitivamente o documento.
A decisão semântica final deve ser feita pelo agente usando este resultado.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError:
    print(
        "Erro: pypdf não está instalado. "
        "Instale com: pip install pypdf",
        file=sys.stderr,
    )
    sys.exit(1)


KEYWORDS: dict[str, list[str]] = {
    "edital": [
        "edital",
        "aviso de licitação",
        "aviso de licitacao",
        "processo licitatório",
        "processo licitatorio",
        "pregão",
        "pregao",
        "concorrência",
        "concorrencia",
        "contratação direta",
        "contratacao direta",
        "dispensa de licitação",
    ],
    "termo_referencia": [
        "termo de referência",
        "termo de referencia",
        "estudo técnico preliminar",
        "estudo tecnico preliminar",
        "especificação técnica",
        "especificacao tecnica",
        "especificações técnicas",
        "especificacoes tecnicas",
        "mapa de riscos",
        "caderno de encargos",
    ],
    "projeto_basico": [
        "projeto básico",
        "projeto basico",
        "projeto executivo",
        "memorial descritivo",
        "laudo de engenharia",
        "laudo de avaliacao",
        "laudo de avaliação",
        "lae",
        "plantas",
    ],
    "termo_compromisso": [
        "termo de compromisso",
        "termo de adesão",
        "termo de adesao",
        "acordo de cooperação",
        "acordo de cooperacao",
        "termo de apostilamento",
    ],
    "contrato": [
        "contrato",
        "instrumento contratual",
        "contratante",
        "contratado",
    ],
    "obra": [
        "obra",
        "construção",
        "construcao",
        "reforma",
        "ampliação",
        "ampliacao",
        "implantação",
        "implantacao",
        "pavimentação",
        "pavimentacao",
        "restauração",
        "restauracao",
        "duplicação",
        "duplicacao",
        "engenharia",
        "empreendimento",
    ],
    "federal": [
        "união",
        "uniao",
        "governo federal",
        "órgão federal",
        "orgao federal",
        "ministério",
        "ministerio",
        "autarquia federal",
        "recurso federal",
        "programa federal",
        "dnit",
        "caixa",
        "fnde",
        "datasus",
        "funasa",
        "transferegov",
        "siconv",
        "pncp",
    ],
    "convenio": [
        "convênio",
        "convenio",
        "convenente",
        "concedente",
    ],
    "instrumento_repasse": [
        "instrumento de repasse",
        "repasse",
        "transferência de recursos",
        "transferencia de recursos",
        "contrato de repasse",
    ],
    "termo_aditivo": [
        "termo aditivo",
        "aditivo contratual",
        "prorrogação",
        "prorrogacao",
        "acréscimo",
        "acrescimo",
        "supressão",
        "supressao",
    ],
    "fiscalizacao": [
        "fiscalização",
        "fiscalizacao",
        "medição",
        "medicao",
        "execução física",
        "execucao fisica",
        "execução financeira",
        "execucao financeira",
    ],
    "auditoria": [
        "auditoria",
        "inspeção",
        "inspecao",
        "irregularidade",
        "relatório",
        "relatorio",
        "tribunal de contas da união",
        "tcu",
    ],
    "obra_paralisada": [
        "obra paralisada",
        "obra parada",
        "paralisação",
        "paralisacao",
        "inativa",
        "interrupção",
        "interrupcao",
    ],
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def count_keywords(full_text: str) -> dict[str, int]:
    normalized = normalize_text(full_text).lower()

    result: dict[str, int] = {}

    for category, terms in KEYWORDS.items():
        count = 0

        for term in terms:
            count += len(
                re.findall(
                    re.escape(term.lower()),
                    normalized,
                )
            )

        result[category] = count

    return result


def choose_sample_pages(page_count: int) -> list[int]:
    """
    Retorna páginas em índice humano (1-based).

    A amostragem é progressiva:
    - documentos pequenos: todas;
    - documentos maiores: início, meio e fim.
    """
    if page_count <= 8:
        return list(range(1, page_count + 1))

    candidates = {
        1,
        2,
        page_count // 2,
        page_count // 2 + 1,
        page_count - 1,
        page_count,
    }

    return sorted(
        page
        for page in candidates
        if 1 <= page <= page_count
    )


def inspect_pdf(
    path: Path,
    requested_pages: list[int] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "file": {
            "name": path.name,
            "path": str(path),
            "size_bytes": 0,
            "sha256": "",
        },
        "pdf": {
            "valid": False,
            "pages": 0,
            "encrypted": False,
        },
        "text": {
            "extractable": False,
            "pages_with_text": 0,
            "total_chars": 0,
        },
        "sample": {
            "pages": [],
            "text": [],
        },
        "keywords": {},
        "signals": {
            "document_types": [],
            "federal": False,
            "public_work": False,
        },
        "errors": [],
    }

    try:
        if not path.exists() or not path.is_file():
            result["errors"].append(f"Arquivo não encontrado ou inválido: {path}")
            return result

        result["file"]["size_bytes"] = path.stat().st_size
        result["file"]["sha256"] = sha256_file(path)

        with path.open("rb") as file:
            magic = file.read(5)

        if magic != b"%PDF-":
            result["errors"].append(
                "Arquivo não possui assinatura PDF válida."
            )
            return result

        reader = PdfReader(str(path))

        result["pdf"]["valid"] = True
        result["pdf"]["pages"] = len(reader.pages)
        result["pdf"]["encrypted"] = reader.is_encrypted

        if reader.is_encrypted:
            result["errors"].append(
                "PDF criptografado. "
                "Conteúdo não foi considerado para classificação."
            )
            return result

        if requested_pages:
            sample_pages = sorted(
                page
                for page in set(requested_pages)
                if 1 <= page <= len(reader.pages)
            )

            if not sample_pages:
                result["errors"].append(
                    "Nenhuma das páginas solicitadas existe no PDF."
                )
                return result
        else:
            sample_pages = choose_sample_pages(len(reader.pages))

        result["sample"]["pages"] = sample_pages

        sample_texts: list[dict[str, Any]] = []
        full_sample_text = ""

        pages_with_text = 0
        total_sample_chars = 0

        for page_number in sample_pages:
            page = reader.pages[page_number - 1]

            try:
                text = page.extract_text() or ""
            except Exception as exc:
                text = ""
                result["errors"].append(
                    f"Erro ao extrair página {page_number}: {exc}"
                )

            text = normalize_text(text)

            if text:
                pages_with_text += 1
                total_sample_chars += len(text)

                sample_texts.append(
                    {
                        "page": page_number,
                        "text": text[:5000],
                    }
                )

                full_sample_text += f" {text}"

        result["sample"]["text"] = sample_texts

        result["text"]["pages_with_text"] = pages_with_text
        result["text"]["total_chars"] = total_sample_chars
        result["text"]["extractable"] = pages_with_text > 0

        keywords = count_keywords(full_sample_text)
        result["keywords"] = keywords

        document_types = []

        if keywords.get("edital", 0) > 0:
            document_types.append("EDITAL")

        if keywords.get("termo_referencia", 0) > 0:
            document_types.append("TERMO_REFERENCIA")

        if keywords.get("projeto_basico", 0) > 0:
            document_types.append("PROJETO_BASICO")

        if keywords.get("termo_compromisso", 0) > 0:
            document_types.append("TERMO_COMPROMISSO")

        if keywords["contrato"] > 0:
            document_types.append("CONTRATO")

        if keywords["termo_aditivo"] > 0:
            document_types.append("TERMO_ADITIVO")

        if keywords["convenio"] > 0:
            document_types.append("CONVENIO")

        if keywords["instrumento_repasse"] > 0:
            document_types.append("INSTRUMENTO_REPASSE")

        if keywords["fiscalizacao"] > 0:
            document_types.append("FISCALIZACAO")

        if keywords["auditoria"] > 0:
            document_types.append("RELATORIO")

        if keywords["obra_paralisada"] > 0:
            document_types.append("OBRA_PARALISADA")

        result["signals"]["document_types"] = document_types
        result["signals"]["federal"] = keywords["federal"] > 0
        result["signals"]["public_work"] = (
            keywords["obra"] > 0
            and (
                keywords.get("edital", 0) > 0
                or keywords.get("termo_referencia", 0) > 0
                or keywords.get("projeto_basico", 0) > 0
                or keywords.get("termo_compromisso", 0) > 0
                or keywords["contrato"] > 0
                or keywords["convenio"] > 0
                or keywords["instrumento_repasse"] > 0
                or keywords["fiscalizacao"] > 0
                or keywords["auditoria"] > 0
            )
        )

        return result

    except Exception as exc:
        result["errors"].append(str(exc))
        return result


def avaliar_pdf(path: Path) -> dict[str, Any]:
    """
    Executa a validação padronizada segundo a skill .antigravity/skills/pdf-validation/SKILL.md.
    Retorna o JSON de validação estruturado com resultado, confiança e evidências.
    """
    inspection = inspect_pdf(path)

    # 1. Integridade básica
    if not inspection["pdf"]["valid"]:
        return {
            "file": path.name,
            "validation": {
                "result": "REJEITADO",
                "confidence": "ALTA",
                "document_type": "DESCONHECIDO",
                "relation_to_public_work": "NAO_RELACIONADO",
                "federal_link": "NAO_FEDERAL",
            },
            "inspection": inspection,
            "evidence": [],
            "notes": inspection["errors"],
        }

    # 2. Extração de texto
    if not inspection["text"]["extractable"]:
        # Se for um PDF válido mas sem texto (possivelmente escaneado)
        return {
            "file": path.name,
            "validation": {
                "result": "VALIDADO_COM_RESSALVAS" if inspection["file"]["size_bytes"] > 50000 else "BLOQUEADO",
                "confidence": "MEDIA" if inspection["file"]["size_bytes"] > 50000 else "BAIXA",
                "document_type": "DIGITALIZADO_OU_IMAGEM",
                "relation_to_public_work": "INDETERMINADA",
                "federal_link": "INDETERMINADO",
            },
            "inspection": inspection,
            "evidence": [],
            "notes": ["PDF sem camada de texto nativa (provavelmente digitalizado)."],
        }

    # 3. Classificação Semântica
    signals = inspection["signals"]
    doc_types = signals["document_types"]
    principal_type = doc_types[0] if doc_types else "OUTRO"

    is_federal = signals["federal"]
    is_work = signals["public_work"] or inspection["keywords"].get("obra", 0) > 0

    evidence = []
    for sample_item in inspection["sample"]["text"]:
        page = sample_item["page"]
        text_lower = sample_item["text"].lower()
        for cat, count in inspection["keywords"].items():
            if count > 0 and any(t in text_lower for t in KEYWORDS[cat]):
                evidence.append({
                    "page": page,
                    "term": cat,
                    "reason": f"Ocorrência de termos da categoria '{cat}'.",
                })
                if len(evidence) >= 5:
                    break
        if len(evidence) >= 5:
            break

    # Decisão final
    if is_federal and is_work and len(doc_types) > 0:
        result_status = "VALIDADO"
        confidence = "ALTA"
        rel_work = "DIRETA"
        fed_link = "FEDERAL"
    elif is_work or is_federal:
        result_status = "VALIDADO_COM_RESSALVAS"
        confidence = "MEDIA"
        rel_work = "DIRETA" if is_work else "INDIRETA"
        fed_link = "FEDERAL" if is_federal else "INDETERMINADO"
    else:
        result_status = "VALIDADO_COM_RESSALVAS" if inspection["text"]["total_chars"] > 200 else "REJEITADO"
        confidence = "BAIXA"
        rel_work = "INDETERMINADA"
        fed_link = "INDETERMINADO"

    return {
        "file": path.name,
        "validation": {
            "result": result_status,
            "confidence": confidence,
            "document_type": principal_type,
            "relation_to_public_work": rel_work,
            "federal_link": fed_link,
        },
        "inspection": inspection,
        "evidence": evidence,
        "notes": inspection["errors"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspeciona PDF e gera JSON compacto."
    )

    parser.add_argument(
        "pdf",
        type=Path,
        help="Caminho do arquivo PDF.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Arquivo JSON de saída. "
        "Se omitido, imprime no stdout.",
    )

    parser.add_argument(
        "--pages",
        type=str,
        help="Páginas específicas a serem analisadas. "
        "Exemplo: --pages 4,5,6",
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        print(
            f"Arquivo não encontrado: {args.pdf}",
            file=sys.stderr,
        )
        return 1

    if not args.pdf.is_file():
        print(
            f"O caminho não é um arquivo: {args.pdf}",
            file=sys.stderr,
        )
        return 1

    requested_pages = None
    if args.pages:
        try:
            requested_pages = [
                int(page.strip())
                for page in args.pages.split(",")
                if page.strip()
            ]
        except ValueError:
            print(
                "Erro: --pages deve conter números separados por vírgula. "
                "Exemplo: --pages 4,5,6",
                file=sys.stderr,
            )
            return 1

    result = inspect_pdf(
        args.pdf,
        requested_pages=requested_pages,
    )

    output = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )

    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            output,
            encoding="utf-8",
        )
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())