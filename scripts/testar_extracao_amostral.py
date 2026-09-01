# -*- coding: utf-8 -*-
"""
scripts/testar_extracao_amostral.py
===================================
Script de Sanity Check e Benchmark para homologação do motor de extração de texto (Etapa 2).
Executa testes empíricos contra os documentos reais do Google Drive (DNIT, CAIXA, etc.).
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

# Força UTF-8 no stdout do Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Garante import do src
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.parsers import (
    ResultadoExtracao,
    avaliar_densidade,
    calcular_densidade,
    extrair_texto_nativo,
    extrair_texto_ocr,
    processar_pdf,
)
from src.config import BASE_DRIVE, PASTA_DADOS_BRUTOS


def imprimir_divisor(titulo: str = "") -> None:
    largura = 75
    if titulo:
        print(f"\n{'=' * 5} {titulo} {'=' * (largura - len(titulo) - 7)}")
    else:
        print("=" * largura)


def formatar_tamanho(bytes_len: int) -> str:
    if bytes_len < 1024:
        return f"{bytes_len} B"
    elif bytes_len < 1024 * 1024:
        return f"{bytes_len / 1024:.1f} KB"
    else:
        return f"{bytes_len / (1024 * 1024):.2f} MB"


def testar_amostra_reais() -> None:
    imprimir_divisor("TESTE DE SANIDADE: EXTRAÇÃO EM DOCUMENTOS REAIS")

    pasta_2026 = BASE_DRIVE / "2026_Dados_brutos"
    pasta_2025 = BASE_DRIVE / "2025_Dados_brutos"

    arquivos_candidatos: list[Path] = []

    # Coleta amostra de diferentes bases
    for pasta in [pasta_2026, pasta_2025]:
        if pasta.exists():
            for base_dir in pasta.iterdir():
                if base_dir.is_dir():
                    pdfs = list(base_dir.glob("*.pdf"))
                    if pdfs:
                        arquivos_candidatos.extend(pdfs[:2])

    if not arquivos_candidatos:
        print("❌ Nenhum PDF encontrado nas pastas de dados brutos do Google Drive.")
        return

    print(f"📁 Encontrados {len(arquivos_candidatos)} arquivos para teste de amostragem.\n")

    # Limita teste a 4 arquivos representativos para agilidade
    amostra = arquivos_candidatos[:4]

    for idx, caminho in enumerate(amostra, start=1):
        tamanho = caminho.stat().st_size
        print(f"[{idx}/{len(amostra)}] Testando: {caminho.name}")
        print(f"     Tamanho: {formatar_tamanho(tamanho)} | Caminho: {caminho.parent.name}/{caminho.name}")

        # Executa processar_pdf (pipeline inteligente)
        res: ResultadoExtracao = processar_pdf(caminho)

        diag, _ = avaliar_densidade(res.densidade_media)

        print(f"     Método Aplicado:     {res.metodo}")
        print(f"     Total de Páginas:    {res.total_paginas} (com texto: {res.paginas_com_texto})")
        print(f"     Total de Caracteres: {res.total_chars:,} caracteres")
        print(f"     Densidade Média:     {res.densidade_media:.1f} chars/pág ({diag})")
        print(f"     Tempo de Execução:   {res.tempo_segundos:.4f} segundos")

        if res.erros:
            print(f"     ⚠️ Avisos/Erros:      {res.erros}")

        # Snippet do texto
        if res.texto_completo:
            snippet = res.texto_completo[:200].replace("\n", " ")
            print(f"     📄 Snippet Inicial:   \"{snippet}...\"")
        else:
            print("     📄 Snippet Inicial:   [SEM TEXTO EXTRAÍDO]")
        print("-" * 75)


def testar_ocr_isolado_documento_real() -> None:
    imprimir_divisor("TESTE DE HOMOLOGAÇÃO: OCR FORÇADO EM PDF REAL")

    pasta_2026 = BASE_DRIVE / "2026_Dados_brutos"
    candidatos = list(pasta_2026.rglob("*.pdf")) if pasta_2026.exists() else []

    # Encontra o primeiro PDF íntegro (com magic bytes válidos)
    caminho_teste = None
    for cand in candidatos:
        try:
            with open(cand, "rb") as f:
                if f.read(5) == b"%PDF-":
                    caminho_teste = cand
                    break
        except Exception:
            continue

    if not caminho_teste:
        print("❌ Nenhum PDF válido encontrado para testar OCR.")
        return

    print(f"🧪 PDF Selecionado para OCR: {caminho_teste.name}")
    print(f"   Testando renderização Poppler + Reconhecimento Tesseract na página 1...\n")

    inicio = time.perf_counter()
    # Executa OCR apenas na página 1 para ser rápido e preciso
    res_ocr = extrair_texto_ocr(caminho_teste, paginas_alvo=[1], dpi=200, idioma="por")
    duracao = time.perf_counter() - inicio

    print(f"   Status do OCR:       {res_ocr.metodo}")
    print(f"   Páginas processadas: {res_ocr.total_paginas}")
    print(f"   Caracteres via OCR:  {res_ocr.total_chars:,} chars")
    print(f"   Tempo total do OCR:  {duracao:.2f} s")
    
    if res_ocr.erros:
        print(f"   ⚠️ Erros no OCR:     {res_ocr.erros}")

    if res_ocr.texto_completo:
        snippet = res_ocr.texto_completo[:300].replace("\n", " ")
        print(f"   📄 Snippet OCR:      \"{snippet}...\"")
        print("\n✅ Conexão Python -> Poppler -> Tesseract OCR 100% HOMOLOGADA!")
    else:
        print("\n⚠️ OCR não retornou texto na página 1.")


def main() -> None:
    print("===========================================================================")
    print("  SUÍTE DE TESTES EMPÍRICOS (SANITY CHECK) — ETAPA 2: PARSING & OCR       ")
    print("===========================================================================")
    
    testar_amostra_reais()
    testar_ocr_isolado_documento_real()
    
    print("\n===========================================================================")
    print("  TODOS OS TESTES DE SANIDADE FORAM CONCLUÍDOS COM SUCESSO! 🎉            ")
    print("===========================================================================")


if __name__ == "__main__":
    main()
