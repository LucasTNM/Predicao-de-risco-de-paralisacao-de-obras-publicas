# -*- coding: utf-8 -*-
"""Limpeza textual determinística (Camada 1) do corpus extraído de PDFs.

As transformações preservam a coesão de frases e parágrafos para os próximos
estágios de RAG/embeddings: esta etapa não remove stopwords.
"""

from __future__ import annotations

from collections import Counter
import re
import unicodedata


# Um caractere de substituição (�) representa informação perdida na extração e
# não pode ser recuperado genericamente. Estes são os vocábulos institucionais
# recorrentes no corpus cujo contexto torna a correção determinística segura.
_CORRECOES_SUBSTITUICAO = {
    "refer�ncia": "referência",
    "licita�o": "licitação",
    "contrata�o": "contratação",
    "execu�o": "execução",
    "or�amento": "orçamento",
    "avalia�o": "avaliação",
    "fiscaliza�o": "fiscalização",
    "administra�o": "administração",
    "documenta�o": "documentação",
    "informa�o": "informação",
    "situa�o": "situação",
    "constru�o": "construção",
    "conclus�o": "conclusão",
    "munic�pio": "município",
    "p�blico": "público",
    "t�cnico": "técnico",
    "n�mero": "número",
    "per�odo": "período",
}

_MOJIBAKE_COMUM = {
    "Ã¡": "á",
    "Ã¢": "â",
    "Ã£": "ã",
    "Ã¤": "ä",
    "Ã©": "é",
    "Ãª": "ê",
    "Ã­": "í",
    "Ã³": "ó",
    "Ã´": "ô",
    "Ãµ": "õ",
    "Ãº": "ú",
    "Ã§": "ç",
    "Ã€": "À",
    "Ã": "Á",
    "Ãƒ": "Ã",
    "Ã‡": "Ç",
    "Ã‰": "É",
    "ÃŠ": "Ê",
    "Ã“": "Ó",
    "Ã”": "Ô",
    "Ãš": "Ú",
    "Ãœ": "Ü",
    "Âº": "º",
    "Âª": "ª",
    "Â°": "°",
    "Â ": " ",
    "â€“": "–",
    "â€”": "—",
    "â€œ": "“",
    "â€": "”",
    "â€˜": "‘",
    "â€™": "’",
}

_NUMERACAO_ISOLADA_RE = re.compile(r"^\s*(?:\d+\.)+\s*$")
_SEPARADOR_VISUAL_RE = re.compile(r"^\s*(?:_{3,}|-{3,}|={3,}|\*{3,})\s*$")
_FIM_DE_FRASE_RE = re.compile(r"[\.:;!?…]\s*$")
_INICIO_MINUSCULO_RE = re.compile(r"^[a-záàâãéêíóôõúüç]")
_MARCADOR_LISTA_RE = re.compile(r"^(?:[-*•▪◦]|\d+[.)])\s+")


def _aplicar_caixa(modelo: str, correcao: str) -> str:
    """Preserva caixa alta/título ao substituir um vocábulo corrompido."""
    if modelo.isupper():
        return correcao.upper()
    # ``str.istitle`` falha quando o termo contém o caractere de substituição �.
    if modelo[:1].isupper():
        return correcao.title()
    return correcao


def normalizar_encoding(texto: str) -> str:
    """Normaliza Unicode e corrige padrões frequentes de mojibake em português.

    Caracteres de substituição sem contexto são trocados por espaço em vez de
    serem inventados. O score de sujeira permite que casos estruturalmente ruins
    sejam encaminhados à Camada 2 opcional.
    """
    if not texto:
        return ""

    texto = (
        texto.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\ufeff", "")
        .replace("\u00a0", " ")
    )
    # NFC recompõe acentos sem converter símbolos semânticos como ``nº`` em ``no``.
    texto = unicodedata.normalize("NFC", texto)

    for padrao, correcao in _CORRECOES_SUBSTITUICAO.items():
        texto = re.sub(
            re.escape(padrao),
            lambda match: _aplicar_caixa(match.group(0), correcao),
            texto,
            flags=re.IGNORECASE,
        )

    for corrompido, correto in _MOJIBAKE_COMUM.items():
        texto = texto.replace(corrompido, correto)

    # Mantém apenas tabulação e quebra de linha entre os controles úteis.
    texto = "".join(
        caractere
        for caractere in texto
        if caractere in ("\n", "\t") or unicodedata.category(caractere) != "Cc"
    )
    return texto.replace("�", " ")


def remover_cabecalhos_repetidos(texto: str) -> str:
    """Remove linhas não vazias repetidas mais de três vezes no documento."""
    if not texto:
        return ""

    linhas = texto.split("\n")
    chaves = [re.sub(r"\s+", " ", linha).strip().casefold() for linha in linhas]
    contagens = Counter(chave for chave in chaves if chave)
    repetidas = {chave for chave, total in contagens.items() if total > 3}

    return "\n".join(linha for linha, chave in zip(linhas, chaves) if chave not in repetidas)


def unificar_quebras_de_linha(texto: str) -> str:
    """Reconstrói linhas de uma frase quebradas por layout de página/coluna."""
    if not texto:
        return ""

    resultado: list[str] = []
    for linha_original in texto.split("\n"):
        linha = linha_original.strip()
        if not linha:
            if resultado and resultado[-1] != "":
                resultado.append("")
            continue

        if resultado and resultado[-1]:
            anterior = resultado[-1]
            deve_unir = (
                not _FIM_DE_FRASE_RE.search(anterior)
                and _INICIO_MINUSCULO_RE.match(linha) is not None
                and _MARCADOR_LISTA_RE.match(anterior) is None
                and _MARCADOR_LISTA_RE.match(linha) is None
            )
            if deve_unir:
                separador = "" if anterior.endswith("-") else " "
                resultado[-1] = f"{anterior.rstrip('-')}{separador}{linha}"
                continue

        resultado.append(linha)

    return "\n".join(resultado)


def remover_numeracao_isolada(texto: str) -> str:
    """Remove linhas contendo exclusivamente numeração de seção (ex.: ``1.2.``)."""
    return "\n".join(linha for linha in texto.split("\n") if not _NUMERACAO_ISOLADA_RE.match(linha))


def limpar_caracteres_especiais(texto: str) -> str:
    """Remove separadores visuais recorrentes na extração de PDFs."""
    return "\n".join(linha for linha in texto.split("\n") if not _SEPARADOR_VISUAL_RE.match(linha))


def normalizar_espacos(texto: str) -> str:
    """Colapsa espaços/tabs horizontais e preserva a separação entre parágrafos."""
    if not texto:
        return ""

    linhas = [re.sub(r"[ \t]+", " ", linha).strip() for linha in texto.split("\n")]
    texto_normalizado = "\n".join(linhas)
    texto_normalizado = re.sub(r"\n{3,}", "\n\n", texto_normalizado)
    return texto_normalizado.strip()


def calcular_score_sujeira(texto: str) -> float:
    """Calcula a proporção de resíduos de extração não linguísticos no texto.

    Pontuação normal, acentos e símbolos monetários não são considerados sujeira;
    são dados úteis. O score mede substituições Unicode, controles, uso privado e
    símbolos gráficos (comuns em tabelas quebradas), que justificam a Camada 2.
    """
    if not texto:
        return 0.0

    def eh_sujo(caractere: str) -> bool:
        categoria = unicodedata.category(caractere)
        return (
            caractere == "�"
            or (categoria == "Cc" and caractere not in {"\n", "\t"})
            or categoria in {"Co", "Cs"}
            or (categoria == "So" and caractere not in {"©", "®", "™"})
        )

    return round(sum(eh_sujo(caractere) for caractere in texto) / len(texto), 6)


def limpar_texto_camada1(texto_bruto: str) -> tuple[str, float]:
    """Executa sequencialmente a Camada 1 e devolve ``(texto, score_final)``."""
    texto = normalizar_encoding(texto_bruto)
    texto = remover_cabecalhos_repetidos(texto)
    texto = unificar_quebras_de_linha(texto)
    texto = remover_numeracao_isolada(texto)
    texto = limpar_caracteres_especiais(texto)
    texto = normalizar_espacos(texto)
    return texto, calcular_score_sujeira(texto)
