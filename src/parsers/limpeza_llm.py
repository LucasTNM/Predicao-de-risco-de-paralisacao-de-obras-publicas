# -*- coding: utf-8 -*-
"""Camada 2 opcional de higienização textual por Gemini.

O módulo não executa nenhuma chamada de rede durante a importação. A ausência de
SDK ou de ``GEMINI_API_KEY`` é comunicada ao orquestrador para que ele persista
com segurança o resultado determinístico da Camada 1.
"""

from __future__ import annotations

from datetime import date
import re
import threading
import time
from typing import Any

from src.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_RPD_LIMIT,
    GEMINI_RPM_LIMIT,
    GEMINI_TEMPERATURA,
)


_PROMPT_SISTEMA = """Você é um assistente de limpeza textual para documentos de obras públicas do governo
federal brasileiro. Sua ÚNICA tarefa é receber um texto extraído de PDF e devolvê-lo
limpo e bem formatado. Regras OBRIGATÓRIAS:
1. Corrija erros de encoding/acentuação (ex.: \"Refer�ncia\" → \"Referência\")
2. Reconstrua tabelas danificadas em formato legível (Markdown simples)
3. Remova cabeçalhos/rodapés de página repetidos
4. Unifique parágrafos que foram quebrados incorretamente
5. NÃO adicione informações, comentários ou explicações
6. NÃO comece sua resposta com \"Aqui está\" ou qualquer introdução
7. Retorne EXCLUSIVAMENTE o texto corrigido, nada mais"""

_INTERVALO_MINIMO = 60.0 / GEMINI_RPM_LIMIT
_LOCK_RATE_LIMIT = threading.Lock()
_ULTIMO_REQUEST = 0.0
_DATA_CONTADOR = date.today()
_REQUESTS_NO_DIA = 0
_PREAMBULO_RE = re.compile(
    r"^\s*(?:aqui\s+est[aá](?:\s+o)?(?:\s+texto)?(?:\s+(?:limpo|corrigido|formatado))?\s*[:\-–—]?|"
    r"texto\s+(?:limpo|corrigido|formatado)\s*[:\-–—]?)\s*(?:\n|$)",
    re.IGNORECASE,
)


class GeminiErro(RuntimeError):
    """Erro base da Camada 2, tratado sem interromper o lote pelo orquestrador."""


class GeminiConfiguracaoError(GeminiErro):
    """Chave ausente ou SDK indisponível."""


class GeminiLimiteDiarioError(GeminiErro):
    """Limite configurado de requisições diárias atingido."""


class GeminiRespostaError(GeminiErro):
    """Resposta sem conteúdo textual aproveitável."""


def _criar_cliente_gemini() -> Any:
    """Inicializa o modelo apenas quando uma chamada à Camada 2 for necessária."""
    if not GEMINI_API_KEY:
        raise GeminiConfiguracaoError(
            "GEMINI_API_KEY não configurada; execute com --skip-llm ou defina uma chave local no .env."
        )

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiConfiguracaoError(
            "SDK google-generativeai não instalada; instale as dependências do projeto."
        ) from exc

    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(model_name=GEMINI_MODEL, system_instruction=_PROMPT_SISTEMA)


def _chunkar_texto(texto: str, max_tokens: int = 3_000) -> list[str]:
    """Divide texto em blocos de aproximadamente ``max_tokens`` sem cortar palavras."""
    if not texto:
        return []
    if max_tokens <= 0:
        raise ValueError("max_tokens deve ser maior que zero")

    limite_caracteres = max_tokens * 4  # aproximação conservadora para PT-BR
    if len(texto) <= limite_caracteres:
        return [texto]

    chunks: list[str] = []
    atual = ""

    def adicionar_trecho(trecho: str) -> None:
        nonlocal atual
        if not trecho:
            return
        if not atual:
            atual = trecho
        elif len(atual) + len(trecho) <= limite_caracteres:
            atual += trecho
        else:
            chunks.append(atual.strip())
            atual = trecho.lstrip()

    for paragrafo in re.split(r"(\n{2,})", texto):
        if not paragrafo:
            continue
        if len(paragrafo) <= limite_caracteres:
            adicionar_trecho(paragrafo)
            continue

        # Parágrafos muito extensos são repartidos mantendo cada palavra inteira.
        for palavra_com_espaco in re.findall(r"\S+\s*", paragrafo):
            adicionar_trecho(palavra_com_espaco)

    if atual.strip():
        chunks.append(atual.strip())
    return chunks


def _aguardar_rate_limit() -> None:
    """Reserva uma requisição respeitando RPM e o teto diário do processo."""
    global _DATA_CONTADOR, _REQUESTS_NO_DIA, _ULTIMO_REQUEST

    with _LOCK_RATE_LIMIT:
        hoje = date.today()
        if hoje != _DATA_CONTADOR:
            _DATA_CONTADOR = hoje
            _REQUESTS_NO_DIA = 0

        if _REQUESTS_NO_DIA >= GEMINI_RPD_LIMIT:
            raise GeminiLimiteDiarioError(
                f"Limite diário configurado para Gemini atingido ({GEMINI_RPD_LIMIT} requisições)."
            )

        agora = time.monotonic()
        espera = _INTERVALO_MINIMO - (agora - _ULTIMO_REQUEST)
        if espera > 0:
            time.sleep(espera)

        _ULTIMO_REQUEST = time.monotonic()
        _REQUESTS_NO_DIA += 1


def _extrair_texto_resposta(resposta: Any) -> str:
    texto = getattr(resposta, "text", None)
    if isinstance(texto, str) and texto.strip():
        return texto.strip()
    raise GeminiRespostaError("Gemini retornou uma resposta sem texto utilizável.")


def _remover_preambulo_resposta(texto: str) -> str:
    """Remove uma introdução indevida curta sem alterar o corpo do documento."""
    return _PREAMBULO_RE.sub("", texto, count=1).strip()


def _enviar_com_rate_limit(cliente: Any, chunk: str, max_tentativas: int = 3) -> str:
    """Envia um bloco ao modelo, com espaçamento entre chamadas e retry para 429."""
    if max_tentativas < 1:
        raise ValueError("max_tentativas deve ser pelo menos 1")

    ultimo_erro: Exception | None = None
    for tentativa in range(max_tentativas):
        _aguardar_rate_limit()
        try:
            resposta = cliente.generate_content(
                chunk,
                generation_config={"temperature": GEMINI_TEMPERATURA},
            )
            texto = _remover_preambulo_resposta(_extrair_texto_resposta(resposta))
            if not texto:
                raise GeminiRespostaError("Gemini retornou somente um preâmbulo sem conteúdo.")
            return texto
        except GeminiErro:
            raise
        except Exception as exc:
            ultimo_erro = exc
            eh_rate_limit = "429" in str(exc) or "resourceexhausted" in type(exc).__name__.lower()
            if not eh_rate_limit or tentativa == max_tentativas - 1:
                raise GeminiErro(f"Falha na chamada Gemini: {exc}") from exc
            time.sleep(2**tentativa)

    raise GeminiErro(f"Falha na chamada Gemini: {ultimo_erro}")


def limpar_texto_camada2(texto_pre_limpo: str, cliente: Any | None = None) -> str:
    """Aplica limpeza contextual ao texto, em chunks sequenciais de ~3.000 tokens."""
    if not texto_pre_limpo:
        return ""

    cliente_gemini = cliente if cliente is not None else _criar_cliente_gemini()
    chunks = _chunkar_texto(texto_pre_limpo)
    respostas = [_enviar_com_rate_limit(cliente_gemini, chunk) for chunk in chunks]
    return "\n\n".join(respostas).strip()


__all__ = [
    "GeminiConfiguracaoError",
    "GeminiErro",
    "GeminiLimiteDiarioError",
    "GeminiRespostaError",
    "limpar_texto_camada2",
]
