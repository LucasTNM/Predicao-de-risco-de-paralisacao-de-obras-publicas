# -*- coding: utf-8 -*-
"""
scripts/verificar_ambiente.py
=============================
Script utilitário para diagnosticar e validar a presença das bibliotecas Python
e dos binários nativos do Windows (Tesseract OCR e Poppler).
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

# Força UTF-8 no stdout do Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def checar_bibliotecas_python() -> dict[str, bool]:
    status = {}
    
    # 1. PyMuPDF (fitz)
    try:
        import fitz
        print(f"✅ PyMuPDF (fitz) {fitz.__version__} — OK")
        status["pymupdf"] = True
    except ImportError as e:
        print(f"❌ PyMuPDF não instalado: {e}")
        status["pymupdf"] = False

    # 2. pytesseract
    try:
        import pytesseract
        print(f"✅ pytesseract {pytesseract.__version__} — OK")
        status["pytesseract"] = True
    except ImportError as e:
        print(f"❌ pytesseract não instalado: {e}")
        status["pytesseract"] = False

    # 3. pdf2image
    try:
        import pdf2image
        print(f"✅ pdf2image — OK")
        status["pdf2image"] = True
    except ImportError as e:
        print(f"❌ pdf2image não instalado: {e}")
        status["pdf2image"] = False

    # 4. Pillow
    try:
        import PIL
        print(f"✅ Pillow {PIL.__version__} — OK")
        status["pillow"] = True
    except ImportError as e:
        print(f"❌ Pillow não instalado: {e}")
        status["pillow"] = False

    # 5. pypdf (legado/inspeção)
    try:
        import pypdf
        print(f"✅ pypdf {pypdf.__version__} — OK")
        status["pypdf"] = True
    except ImportError as e:
        print(f"⚠️ pypdf não instalado: {e}")
        status["pypdf"] = False

    return status


def checar_binarios_sistema() -> dict[str, bool]:
    status = {}
    print("\n--- Verificação de Binários Nativos (Windows) ---")

    # 1. Tesseract OCR
    tesseract_no_path = shutil.which("tesseract")
    caminho_padrao_tesseract = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    
    if tesseract_no_path:
        print(f"✅ Tesseract OCR detectado no PATH: {tesseract_no_path}")
        status["tesseract"] = True
    elif caminho_padrao_tesseract.exists():
        print(f"✅ Tesseract OCR detectado em: {caminho_padrao_tesseract}")
        status["tesseract"] = True
    else:
        print("❌ Tesseract OCR NÃO encontrado.")
        print("   👉 Instale o instalador 64-bit com suporte ao Português (por.traineddata):")
        print("   👉 https://github.com/UB-Mannheim/tesseract/wiki")
        status["tesseract"] = False

    # 2. Poppler (pdftoppm)
    poppler_no_path = shutil.which("pdftoppm")
    caminhos_poppler_comuns = [
        Path(r"C:\poppler\Library\bin\pdftoppm.exe"),
        Path(r"C:\poppler\bin\pdftoppm.exe"),
        Path(r"C:\Program Files\poppler\bin\pdftoppm.exe"),
    ]
    poppler_encontrado = None
    if poppler_no_path:
        poppler_encontrado = poppler_no_path
    else:
        for p in caminhos_poppler_comuns:
            if p.exists():
                poppler_encontrado = str(p)
                break

    if poppler_encontrado:
        print(f"✅ Poppler (pdftoppm) detectado: {poppler_encontrado}")
        status["poppler"] = True
    else:
        print("❌ Poppler NÃO encontrado.")
        print("   👉 Baixe os binários de: https://github.com/oschwartz10612/poppler-windows/releases")
        print("   👉 Extraia para C:\\poppler\\ e adicione a pasta Library\\bin ao PATH.")
        status["poppler"] = False

    return status


def main() -> int:
    print("=== Diagnóstico de Ambiente: Extração de Texto & OCR ===\n")
    py_ok = checar_bibliotecas_python()
    bin_ok = checar_binarios_sistema()

    print("\n=======================================================")
    todos_py = all(py_ok.values())
    todos_bin = all(bin_ok.values())

    if todos_py and todos_bin:
        print("🎉 Ambiente 100% pronto para extração nativa e OCR!")
        return 0
    elif todos_py:
        print("⚠️ Bibliotecas Python instaladas, mas os binários nativos (Tesseract/Poppler) ainda precisam ser instalados ou configurados.")
        return 1
    else:
        print("❌ Existem pendências de instalação.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
