# -*- coding: utf-8 -*-
"""
src/parsers/pdf_to_text.py
==========================
Motor de extração textual de alta performance para PDFs de processos licitatórios
e auditoria de obras públicas federais.

Suporta extração nativa via PyMuPDF (fitz) e prepara a base para a esteira
de fallback com OCR (Tesseract / pdf2image).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import shutil
import time
from typing import Any, Literal

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore

try:
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore

try:
    import pdf2image
except ImportError:
    pdf2image = None  # type: ignore

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
except ImportError:
    Image = None  # type: ignore

from src.parsers.exceptions import (
    PdfCorruptError,
    PdfEncryptedError,
    PdfIOError,
    PdfOcrFailError,
    PdfParsingError,
    retry_on_io_error,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DE CONFIGURAÇÃO E LIMIARES DE OCR
# ─────────────────────────────────────────────────────────────────────────────

# Localização padrão do Tesseract OCR no Windows
_CAMINHO_TESSERACT_PADRAO = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

# Configura o caminho do binário do Tesseract no pytesseract se necessário
if pytesseract is not None:
    if not shutil.which("tesseract") and _CAMINHO_TESSERACT_PADRAO.exists():
        pytesseract.pytesseract.tesseract_cmd = str(_CAMINHO_TESSERACT_PADRAO)

# Limiares de Densidade Textual (caracteres úteis / página)
LIMIAR_DENSIDADE_NATIVO: float = 200.0   # >= 200: Texto nativo rico (Aceitar nativo)
LIMIAR_DENSIDADE_PARCIAL: float = 50.0   # 50-199: Texto parcial/corrompido (OCR nas páginas vazias)
                                        # < 50: Scan puro / imagem (OCR completo no documento)

# Limite mínimo total de caracteres para validar um PDF extraído
LIMIAR_MIN_CHARS_TOTAL: int = 100       # < 100 total após OCR: IRRECUPERAVEL

# Resolução DPI padrão para rasterização em OCR (equilíbrio ideal velocidade x acurácia)
DPI_OCR_PADRAO: int = 200


MetodoExtracao = Literal["NATIVO", "OCR", "NATIVO+OCR", "IRRECUPERAVEL", "ERRO"]


@dataclass
class ResultadoExtracao:
    """
    Estrutura consolidada de resultado de extração textual de um PDF.
    """
    texto_completo: str = ""
    total_chars: int = 0
    total_paginas: int = 0
    paginas_com_texto: int = 0
    metodo: MetodoExtracao = "NATIVO"
    tempo_segundos: float = 0.0
    erros: list[str] = field(default_factory=list)

    @property
    def densidade_media(self) -> float:
        """Retorna a média de caracteres por página."""
        if self.total_paginas <= 0:
            return 0.0
        return self.total_chars / self.total_paginas

    @property
    def sucesso(self) -> bool:
        """Indica se houve extração de texto útil."""
        return self.total_chars > 0 and len(self.erros) == 0


def normalizar_texto_extraido(texto: str) -> str:
    """
    Higieniza o texto bruto extraído do PDF:
    - Remove caracteres nulos e de controle indesejados.
    - Normaliza espaços contínuos e quebras excessivas de linha.
    """
    if not texto:
        return ""
    
    # Remove bytes nulos
    texto = texto.replace("\x00", "")
    
    # Normaliza quebras de linha e múltiplos espaços horizontais
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    
    return texto.strip()


@retry_on_io_error(max_retries=3, base_delay=2.0)
def extrair_texto_nativo(caminho_pdf: Path | str) -> ResultadoExtracao:
    """
    Motor primário de extração textual de alto desempenho baseado em PyMuPDF (fitz).

    Parâmetros:
    -----------
    caminho_pdf: Caminho para o arquivo PDF a ser processado.

    Retorna:
    --------
    ResultadoExtracao: Instância contendo o texto extraído, contagem de páginas,
                       densidade e métricas de execução.
    """
    inicio = time.perf_counter()
    caminho = Path(caminho_pdf)
    resultado = ResultadoExtracao(metodo="NATIVO")

    if fitz is None:
        resultado.erros.append("Biblioteca PyMuPDF (fitz) não está instalada no ambiente.")
        resultado.metodo = "ERRO"
        resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return resultado

    if not caminho.exists() or not caminho.is_file():
        resultado.erros.append(f"Arquivo não encontrado ou inválido: {caminho}")
        resultado.metodo = "ERRO"
        resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return resultado

    try:
        # Abre o documento via PyMuPDF
        with fitz.open(str(caminho)) as doc:
            resultado.total_paginas = len(doc)

            if doc.is_encrypted:
                resultado.erros.append("PDF criptografado ou protegido por senha.")
                resultado.metodo = "ERRO"
                resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
                return resultado

            if resultado.total_paginas == 0:
                resultado.erros.append("PDF vazio (0 páginas).")
                resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
                return resultado

            paginas_texto: list[str] = []
            paginas_com_conteudo = 0

            for num_pagina in range(resultado.total_paginas):
                try:
                    pagina = doc.load_page(num_pagina)
                    # Extrai texto bruto da página
                    texto_pag = pagina.get_text("text") or ""
                    texto_pag_limpo = normalizar_texto_extraido(texto_pag)

                    if texto_pag_limpo:
                        paginas_com_conteudo += 1
                        paginas_texto.append(texto_pag_limpo)
                except Exception as exc_pag:
                    resultado.erros.append(f"Falha ao extrair página {num_pagina + 1}: {exc_pag}")

            resultado.paginas_com_texto = paginas_com_conteudo
            texto_unificado = "\n\n".join(paginas_texto)
            resultado.texto_completo = texto_unificado
            resultado.total_chars = len(texto_unificado)

    except fitz.FileDataError as exc:
        resultado.erros.append(f"PDF corrompido ou formato inválido: {exc}")
        resultado.metodo = "ERRO"
    except Exception as exc:
        resultado.erros.append(f"Erro inesperado durante extração nativa: {exc}")
        resultado.metodo = "ERRO"

    resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# TAREFA 2.3 — MÉTRICA DE DENSIDADE E LIMIARES DE DECISÃO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_densidade(resultado: ResultadoExtracao | tuple[int, int] | int, total_paginas: int | None = None) -> float:
    """
    Calcula a densidade média de caracteres úteis por página do PDF.

    Parâmetros:
    -----------
    resultado: Pode ser uma instância de ResultadoExtracao, uma tupla (total_chars, total_paginas)
               ou um inteiro representando total_chars.
    total_paginas: Total de páginas (usado caso o primeiro argumento seja int).

    Retorna:
    --------
    float: Densidade média de caracteres por página.
    """
    if isinstance(resultado, ResultadoExtracao):
        total_chars = resultado.total_chars
        pags = resultado.total_paginas
    elif isinstance(resultado, tuple):
        total_chars, pags = resultado
    else:
        total_chars = int(resultado)
        pags = total_paginas if total_paginas is not None else 1

    pags = max(pags, 1)
    return round(total_chars / pags, 2)


def avaliar_densidade(densidade: float) -> tuple[str, str]:
    """
    Avalia a densidade de caracteres e determina a estratégia necessária.

    Retorna:
    --------
    tuple[str, str]: (Diagnóstico, Ação recomendada)
    - >= 200: ("Texto nativo rico", "ACEITAR_NATIVO")
    - 50-199: ("Texto parcial/corrompido", "OCR_PAGINAS_VAZIAS")
    - < 50:   ("Scan puro / imagem", "OCR_COMPLETO")
    """
    if densidade >= LIMIAR_DENSIDADE_NATIVO:
        return "Texto nativo rico", "ACEITAR_NATIVO"
    elif densidade >= LIMIAR_DENSIDADE_PARCIAL:
        return "Texto parcial/corrompido", "OCR_PAGINAS_VAZIAS"
    else:
        return "Scan puro / imagem", "OCR_COMPLETO"


# ─────────────────────────────────────────────────────────────────────────────
# TAREFA 2.4 — MOTOR SECUNDÁRIO DE OCR COM PRÉ-PROCESSAMENTO
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_limiar_otsu(imagem_l: Any) -> int:
    """
    Calcula o limiar ótimo de binarização de Otsu a partir do histograma da imagem em tons de cinza.
    Algoritmo 100% nativo em Python, sem dependência do OpenCV.
    """
    hist = imagem_l.histogram()
    total = imagem_l.width * imagem_l.height
    if total == 0:
        return 128

    soma_total = sum(i * hist[i] for i in range(256))
    soma_b = 0.0
    peso_b = 0.0
    variancia_max = 0.0
    limiar_otimo = 128

    for t in range(256):
        peso_b += hist[t]
        if peso_b == 0:
            continue
        peso_f = total - peso_b
        if peso_f == 0:
            break
        soma_b += t * hist[t]
        media_b = soma_b / peso_b
        media_f = (soma_total - soma_b) / peso_f
        var_entre_classes = peso_b * peso_f * ((media_b - media_f) ** 2)

        if var_entre_classes > variancia_max:
            variancia_max = var_entre_classes
            limiar_otimo = t

    return limiar_otimo


def preprocessar_imagem_ocr(imagem: Any) -> Any:
    """
    Aplica pipeline de melhoria de qualidade na imagem para maximizar a precisão do Tesseract:
    1. Conversão para escala de cinza ('L').
    2. Realce de contraste.
    3. Binarização adaptativa de Otsu (separa fundo e texto perfeitamente).
    """
    if Image is None or imagem is None:
        return imagem

    try:
        # 1. Escala de cinza
        img_gray = imagem.convert("L")

        # 2. Realce de contraste moderado
        enhancer = ImageEnhance.Contrast(img_gray)
        img_contrast = enhancer.enhance(1.5)

        # 3. Binarização Otsu
        limiar = _calcular_limiar_otsu(img_contrast)
        img_binaria = img_contrast.point(lambda p: 255 if p > limiar else 0, mode="1")

        return img_binaria
    except Exception:
        # Em caso de qualquer falha na transformação, retorna imagem original
        return imagem


@retry_on_io_error(max_retries=3, base_delay=2.0)
def extrair_texto_ocr(
    caminho_pdf: Path | str,
    paginas_alvo: list[int] | None = None,
    dpi: int = DPI_OCR_PADRAO,
    idioma: str = "por",
    aplicar_preprocessamento: bool = True,
) -> ResultadoExtracao:
    """
    Motor secundário de extração de texto via OCR (pytesseract + pdf2image / Poppler).

    Parâmetros:
    -----------
    caminho_pdf: Caminho do arquivo PDF.
    paginas_alvo: Lista opcional de índices de páginas (1-indexed) a serem processadas via OCR.
                  Se None, processa todas as páginas do PDF.
    dpi: Resolução de renderização das páginas (padrão 200 DPI).
    idioma: Pacote de idioma do Tesseract (padrão 'por' para Português).
    aplicar_preprocessamento: Se True, aplica escala de cinza e binarização Otsu antes do OCR.

    Retorna:
    --------
    ResultadoExtracao: Objeto estruturado com texto extraído e métricas de desempenho.
    """
    inicio = time.perf_counter()
    caminho = Path(caminho_pdf)
    resultado = ResultadoExtracao(metodo="OCR")

    if pytesseract is None or pdf2image is None:
        resultado.erros.append("pytesseract ou pdf2image não estão disponíveis no ambiente.")
        resultado.metodo = "ERRO"
        resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return resultado

    if not caminho.exists() or not caminho.is_file():
        resultado.erros.append(f"Arquivo não encontrado: {caminho}")
        resultado.metodo = "ERRO"
        resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return resultado

    try:
        # Obter informações do total de páginas com PyMuPDF se disponível ou via pdf2image
        total_pags = 0
        if fitz is not None:
            try:
                with fitz.open(str(caminho)) as doc:
                    total_pags = len(doc)
            except Exception:
                pass

        # Converte páginas do PDF em imagens PIL
        # Se paginas_alvo for informado para um range contíguo ou pontual, otimiza conversão
        imagens: list[tuple[int, Any]] = []

        if paginas_alvo and len(paginas_alvo) == 1:
            num_pag = paginas_alvo[0]
            imgs = pdf2image.convert_from_path(
                str(caminho),
                dpi=dpi,
                first_page=num_pag,
                last_page=num_pag,
            )
            if imgs:
                imagens.append((num_pag, imgs[0]))
        else:
            # Converte documento completo e seleciona as páginas alvo
            todas_imgs = pdf2image.convert_from_path(str(caminho), dpi=dpi)
            if total_pags == 0:
                total_pags = len(todas_imgs)

            for i, img in enumerate(todas_imgs, start=1):
                if paginas_alvo is None or i in paginas_alvo:
                    imagens.append((i, img))

        resultado.total_paginas = total_pags if total_pags > 0 else len(imagens)

        paginas_texto: list[str] = []
        paginas_com_conteudo = 0

        for num_pag, img in imagens:
            try:
                img_para_ocr = preprocessar_imagem_ocr(img) if aplicar_preprocessamento else img
                texto_pag = pytesseract.image_to_string(img_para_ocr, lang=idioma)
                texto_pag_limpo = normalizar_texto_extraido(texto_pag)

                if texto_pag_limpo:
                    paginas_com_conteudo += 1
                    paginas_texto.append(texto_pag_limpo)
            except Exception as exc_ocr:
                resultado.erros.append(f"Falha de OCR na página {num_pag}: {exc_ocr}")

        resultado.paginas_com_texto = paginas_com_conteudo
        texto_unificado = "\n\n".join(paginas_texto)
        resultado.texto_completo = texto_unificado
        resultado.total_chars = len(texto_unificado)

    except Exception as exc:
        resultado.erros.append(f"Erro geral no pipeline de OCR: {exc}")
        resultado.metodo = "ERRO"

    resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# TAREFA 2.5 — ORQUESTRADOR PRINCIPAL COM FALLBACK INTELIGENTE
# ─────────────────────────────────────────────────────────────────────────────

def processar_pdf(
    caminho_pdf: Path | str,
    forcar_ocr: bool = False,
    dpi: int = DPI_OCR_PADRAO,
    idioma: str = "por",
    raise_on_error: bool = False,
) -> ResultadoExtracao:
    """
    Função principal e unificada de extração textual com fallback inteligente e blindagem de erros.

    Fluxo de Execução:
    ------------------
    1. Valida integridade do arquivo (existência, tamanho > 0, magic bytes %PDF-).
    2. Executa extração nativa de alta velocidade via PyMuPDF (com retries automáticos para I/O).
    3. Calcula densidade média de caracteres por página:
       - Se densidade >= 200 chars/página: Aceita extração nativa imediatamente (O(1) ms).
       - Se 50 <= densidade < 200 chars/página: Executa OCR seletivo apenas nas páginas vazias (Modo Híbrido).
       - Se densidade < 50 chars/página: Executa OCR completo em todo o documento (Modo Scan Puro).
    4. Avalia volume final extraído:
       - Se total_chars < 100 caracteres após todas as tentativas: Classifica como IRRECUPERAVEL.
    5. Retorna o ResultadoExtracao com método consolidado e métricas completas de tempo e densidade.

    Parâmetros:
    -----------
    caminho_pdf: Caminho do arquivo PDF no disco ou Google Drive.
    forcar_ocr: Se True, ignora extração nativa e força OCR em todas as páginas.
    dpi: Resolução DPI para renderização do OCR (padrão 200).
    idioma: Idioma do Tesseract OCR (padrão 'por').
    raise_on_error: Se True, levanta exceções customizadas (PdfCorruptError, PdfEncryptedError, etc.).

    Retorna:
    --------
    ResultadoExtracao: Resultado consolidado com texto, contagens, método e diagnósticos.
    """
    inicio = time.perf_counter()
    caminho = Path(caminho_pdf)
    resultado = ResultadoExtracao()

    # 1. Validações de integridade básicas
    if not caminho.exists() or not caminho.is_file():
        msg = f"Arquivo não encontrado: {caminho}"
        if raise_on_error:
            raise PdfIOError(msg, caminho_pdf=caminho)
        resultado.erros.append(msg)
        resultado.metodo = "ERRO"
        resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return resultado

    if caminho.stat().st_size == 0:
        msg = f"Arquivo com 0 bytes: {caminho.name}"
        if raise_on_error:
            raise PdfCorruptError(msg, caminho_pdf=caminho)
        resultado.erros.append(msg)
        resultado.metodo = "ERRO"
        resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return resultado

    try:
        with open(caminho, "rb") as f:
            magic_bytes = f.read(5)
        if magic_bytes != b"%PDF-":
            msg = f"Arquivo não possui assinatura válida de cabeçalho PDF (%PDF-): {caminho.name}"
            if raise_on_error:
                raise PdfCorruptError(msg, caminho_pdf=caminho)
            resultado.erros.append(msg)
            resultado.metodo = "ERRO"
            resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
            return resultado
    except (OSError, PermissionError, IOError) as exc:
        msg = f"Falha de I/O ao ler cabeçalho do arquivo: {exc}"
        if raise_on_error:
            raise PdfIOError(msg, caminho_pdf=caminho) from exc
        resultado.erros.append(msg)
        resultado.metodo = "ERRO"
        resultado.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return resultado

    # Se forçado OCR direto
    if forcar_ocr:
        res_ocr = extrair_texto_ocr(caminho, dpi=dpi, idioma=idioma)
        res_ocr.tempo_segundos = round(time.perf_counter() - inicio, 4)
        if res_ocr.total_chars < LIMIAR_MIN_CHARS_TOTAL:
            res_ocr.metodo = "IRRECUPERAVEL"
            msg = f"Documento com volume textual insuficiente ({res_ocr.total_chars} < {LIMIAR_MIN_CHARS_TOTAL}) mesmo via OCR forçado."
            res_ocr.erros.append(msg)
            if raise_on_error:
                raise PdfOcrFailError(msg, caminho_pdf=caminho)
        return res_ocr

    # 2. Tentativa primária: Extração Nativa de Alta Velocidade (PyMuPDF)
    res_nativo = extrair_texto_nativo(caminho)

    # Se a extração nativa falhar por criptografia ou arquivo corrompido que inviabilize leitura
    if res_nativo.metodo == "ERRO":
        # Se for erro de criptografia
        if any("criptografado" in err.lower() for err in res_nativo.erros):
            res_nativo.tempo_segundos = round(time.perf_counter() - inicio, 4)
            if raise_on_error:
                raise PdfEncryptedError(f"PDF protegido por senha: {caminho.name}", caminho_pdf=caminho)
            return res_nativo
        
        # Caso seja falha de parsing interno do fitz mas o PDF exista, tenta fallback para OCR completo
        res_ocr = extrair_texto_ocr(caminho, dpi=dpi, idioma=idioma)
        res_ocr.erros.extend(res_nativo.erros)
        res_ocr.tempo_segundos = round(time.perf_counter() - inicio, 4)
        if res_ocr.total_chars < LIMIAR_MIN_CHARS_TOTAL:
            res_ocr.metodo = "IRRECUPERAVEL"
            if raise_on_error:
                raise PdfOcrFailError(f"Falha de OCR após erro nativo em {caminho.name}", caminho_pdf=caminho)
        return res_ocr

    # 3. Métrica de densidade
    densidade = res_nativo.densidade_media
    _, acao = avaliar_densidade(densidade)

    # 4. Caso A: Texto nativo rico (>= 200 chars/página ou >= 800 chars nativos já validados pelo Gatekeeper)
    if acao == "ACEITAR_NATIVO" or res_nativo.total_chars >= 800:
        res_nativo.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return res_nativo

    # 5. Caso B: Texto parcial / páginas vazias mistas (50 <= densidade < 200)
    elif acao == "OCR_PAGINAS_VAZIAS":
        paginas_textos: dict[int, str] = {}
        paginas_sem_texto: list[int] = []

        try:
            with fitz.open(str(caminho)) as doc:
                for i in range(len(doc)):
                    num_p = i + 1
                    txt_p = normalizar_texto_extraido(doc.load_page(i).get_text("text") or "")
                    if txt_p:
                        paginas_textos[num_p] = txt_p
                    else:
                        paginas_sem_texto.append(num_p)
        except Exception:
            paginas_sem_texto = []

        # Se existirem páginas vazias, processa OCR apenas nelas
        if paginas_sem_texto:
            res_ocr_parcial = extrair_texto_ocr(caminho, paginas_alvo=paginas_sem_texto, dpi=dpi, idioma=idioma)
            
            # Se o OCR recuperou texto nas páginas vazias
            if res_ocr_parcial.total_chars > 0:
                try:
                    textos_ocr_separados = res_ocr_parcial.texto_completo.split("\n\n")
                    for p_num, txt_ocr in zip(paginas_sem_texto, textos_ocr_separados):
                        txt_limpo = normalizar_texto_extraido(txt_ocr)
                        if txt_limpo:
                            paginas_textos[p_num] = txt_limpo
                except Exception:
                    pass

                # Remonta o documento ordenadamente de 1 a N
                total_pags = res_nativo.total_paginas
                paginas_finais = [paginas_textos[p] for p in range(1, total_pags + 1) if p in paginas_textos and paginas_textos[p]]
                
                texto_mesclado = "\n\n".join(paginas_finais)
                res_hibrido = ResultadoExtracao(
                    texto_completo=texto_mesclado,
                    total_chars=len(texto_mesclado),
                    total_paginas=total_pags,
                    paginas_com_texto=len(paginas_finais),
                    metodo="NATIVO+OCR",
                    tempo_segundos=round(time.perf_counter() - inicio, 4),
                    erros=res_nativo.erros + res_ocr_parcial.erros,
                )
                return res_hibrido

        # Se não havia páginas vazias ou OCR parcial não trouxe ganho, aceita nativo existente
        res_nativo.tempo_segundos = round(time.perf_counter() - inicio, 4)
        return res_nativo

    # 6. Caso C: Scan puro / imagem (< 50 chars/página) -> OCR Completo
    else:
        res_ocr = extrair_texto_ocr(caminho, dpi=dpi, idioma=idioma)
        res_ocr.tempo_segundos = round(time.perf_counter() - inicio, 4)

        # 7. Checagem de irrecuperabilidade (< 100 caracteres no total)
        if res_ocr.total_chars < LIMIAR_MIN_CHARS_TOTAL:
            res_ocr.metodo = "IRRECUPERAVEL"
            msg = f"Volume textual insuficiente ({res_ocr.total_chars} chars < {LIMIAR_MIN_CHARS_TOTAL}) mesmo após OCR completo."
            res_ocr.erros.append(msg)
            if raise_on_error:
                raise PdfOcrFailError(msg, caminho_pdf=caminho)

        return res_ocr
