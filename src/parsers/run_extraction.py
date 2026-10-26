# -*- coding: utf-8 -*-
"""
src/parsers/run_extraction.py
=============================
Orquestrador CLI de produção para extração massiva de texto (PDF -> TXT) e OCR
sobre o corpus de obras públicas federais persistido no Google Drive.

Possui:
- Blindagem contra falhas (continue-on-error).
- Pulo instantâneo em O(1) de arquivos já processados (Pause & Resume).
- Suporte a concorrência paralela Multi-Thread (ThreadPoolExecutor).
- Padrão transacional Write-Ahead em disco/Google Drive.
- Relatório estatístico consolidado com métricas de throughput.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import datetime
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import threading
import time
from typing import Any

# Força UTF-8 no console do Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Garante path de import do src
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import (
    ANO_BASE,
    ANOS_PAINEL_TCU,
    BASE_DRIVE,
    BASES_SUPORTADAS,
    PASTA_DADOS_BRUTOS,
    PASTA_TEXTOS_EXTRAIDOS,
    logger,
    obter_pasta_textos_base,
)
from src.parsers.exceptions import (
    PdfCorruptError,
    PdfEncryptedError,
    PdfIOError,
    PdfOcrFailError,
    PdfParsingError,
)
from src.parsers.pdf_to_text import (
    DPI_OCR_PADRAO,
    ResultadoExtracao,
    processar_pdf,
)
from src.parsers.storage import (
    _LOCK_LOG_EXTRACAO,
    carregar_pdfs_ja_processados,
    inicializar_log_extracao_csv,
    salvar_texto_e_registrar_log,
)
from src.utils import eh_ficha_sintetica_legada

_LOCK_CROSS_TXT = threading.Lock()
_INDICE_CROSS_TXT: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
_CROSS_TXT_CARREGADO = False


def _carregar_indice_cross_ano_txt() -> dict[tuple[str, str], tuple[Path, dict[str, Any]]]:
    """
    Carrega em memória O(1) os textos já extraídos em qualquer safra (`2022`..`2026`):
    `(base_lower, nome_pdf) -> (caminho_txt, metadados_log)`
    """
    global _CROSS_TXT_CARREGADO
    with _LOCK_CROSS_TXT:
        if _CROSS_TXT_CARREGADO:
            return _INDICE_CROSS_TXT
        for ano in ANOS_PAINEL_TCU:
            pasta_txt_ano = BASE_DRIVE / f"{ano}_Textos_extraidos"
            csv_path = pasta_txt_ano / "log_extracao.csv"
            if not csv_path.exists():
                continue
            try:
                with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                    for row in csv.DictReader(f):
                        status = (row.get("status") or "").strip().upper()
                        if status not in ("OK", "OCR_PARCIAL"):
                            continue
                        base_l = (row.get("base_de_dados") or "").strip().lower()
                        nome_pdf = (row.get("nome_pdf") or "").strip()
                        nome_txt = (row.get("nome_txt") or "").strip()
                        if not base_l or not nome_pdf or not nome_txt or eh_ficha_sintetica_legada(nome_pdf):
                            continue
                        caminho_txt = pasta_txt_ano / base_l / nome_txt
                        _INDICE_CROSS_TXT.setdefault((base_l, nome_pdf), (caminho_txt, dict(row)))
            except Exception:
                pass
        _CROSS_TXT_CARREGADO = True
        return _INDICE_CROSS_TXT


@dataclass
class EstatisticasExtracao:
    """Consolidador estatístico da execução batch."""
    total_encontrados: int = 0
    pulos_idempotencia: int = 0
    processados_lote: int = 0
    sucesso_nativo: int = 0
    sucesso_hibrido: int = 0
    sucesso_ocr: int = 0
    falhas_corrompidos: int = 0
    falhas_criptografados: int = 0
    falhas_irrecuperaveis: int = 0
    falhas_io: int = 0
    falhas_outras: int = 0
    total_chars_extraidos: int = 0
    tempo_total_segundos: float = 0.0


def processar_um_arquivo(
    caminho_pdf: Path,
    pasta_saida_base: Path,
    ano_base: str,
    base_nome: str,
    cache_log: dict[tuple[str, str, str], str],
    caminho_csv: Path,
    forcar_ocr: bool = False,
    dpi: int = DPI_OCR_PADRAO,
) -> tuple[str, ResultadoExtracao]:
    """
    Processa um único PDF com blindagem total contra exceções e reuso Cross-Ano O(1).
    Nunca propaga exceções para não interromper a thread/loop principal.
    """
    caminho_txt = pasta_saida_base / f"{caminho_pdf.stem}.txt"
    chave_cross = (str(base_nome).strip().lower(), caminho_pdf.name.strip())

    # Aguarda reconexão caso o Google Drive Desktop (G:\) sofra micro-desconexão durante sync pesado
    for _ in range(30):
        if BASE_DRIVE.exists():
            break
        time.sleep(2.0)

    try:
        if not forcar_ocr and chave_cross in _INDICE_CROSS_TXT:
            src_txt, meta = _INDICE_CROSS_TXT[chave_cross]
            if src_txt.exists() and src_txt.stat().st_size > 0:
                if src_txt.resolve() != caminho_txt.resolve() and not caminho_txt.exists():
                    caminho_txt.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_txt, caminho_txt)
                tot_chars = int(meta.get("total_chars") or 0)
                tot_pags = int(meta.get("total_paginas") or 1)
                metodo_m = str(meta.get("metodo_extracao") or "NATIVO")
                status_m = str(meta.get("status") or "OK")
                hash_m = str(meta.get("sha256_pdf") or "")
                res_reuso = ResultadoExtracao(
                    texto_completo="",
                    total_chars=tot_chars,
                    total_paginas=tot_pags,
                    paginas_com_texto=tot_pags,
                    metodo=metodo_m,  # type: ignore[arg-type]
                    tempo_segundos=0.001,
                )
                chave_log = (str(ano_base).strip(), str(base_nome).strip().lower(), caminho_pdf.name.strip())
                with _LOCK_LOG_EXTRACAO:
                    inicializar_log_extracao_csv(caminho_csv)
                    with open(caminho_csv, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            datetime.datetime.now().isoformat(),
                            ano_base,
                            base_nome.strip().lower(),
                            caminho_pdf.name,
                            caminho_txt.name,
                            metodo_m,
                            tot_pags,
                            tot_chars,
                            f"{res_reuso.densidade_media:.2f}",
                            "0.0010",
                            status_m,
                            hash_m,
                            f"Reuso Cross-Ano O(1) ({src_txt.parent.parent.name})",
                        ])
                    cache_log[chave_log] = status_m
                return "SUCESSO_NATIVO", res_reuso

        # Executa extração com tratamento de erro granular
        resultado = processar_pdf(
            caminho_pdf=caminho_pdf,
            forcar_ocr=forcar_ocr,
            dpi=dpi,
            raise_on_error=True,
        )

        salvar_texto_e_registrar_log(
            caminho_pdf=caminho_pdf,
            caminho_txt=caminho_txt,
            resultado=resultado,
            ano_base=ano_base,
            base_nome=base_nome,
            cache_log=cache_log,
            caminho_csv=caminho_csv,
        )

        if resultado.total_chars > 0 and caminho_txt.exists():
            with _LOCK_CROSS_TXT:
                _INDICE_CROSS_TXT.setdefault(
                    chave_cross,
                    (
                        caminho_txt,
                        {
                            "metodo_extracao": resultado.metodo,
                            "total_paginas": str(resultado.total_paginas),
                            "total_chars": str(resultado.total_chars),
                            "status": "OCR_PARCIAL" if resultado.metodo == "NATIVO+OCR" else "OK",
                            "sha256_pdf": "",
                        },
                    ),
                )

        if resultado.metodo == "NATIVO":
            status_retorno = "SUCESSO_NATIVO"
        elif resultado.metodo == "NATIVO+OCR":
            status_retorno = "SUCESSO_HIBRIDO"
        elif resultado.metodo == "OCR":
            status_retorno = "SUCESSO_OCR"
        else:
            status_retorno = "OK"

        return status_retorno, resultado

    except PdfCorruptError as exc:
        res_erro = ResultadoExtracao(metodo="ERRO", erros=[str(exc)])
        salvar_texto_e_registrar_log(
            caminho_pdf, caminho_txt, res_erro, ano_base, base_nome, cache_log, caminho_csv
        )
        return "CORROMPIDO", res_erro

    except PdfEncryptedError as exc:
        res_erro = ResultadoExtracao(metodo="ERRO", erros=[str(exc)])
        salvar_texto_e_registrar_log(
            caminho_pdf, caminho_txt, res_erro, ano_base, base_nome, cache_log, caminho_csv
        )
        return "CRIPTOGRAFADO", res_erro

    except PdfOcrFailError as exc:
        res_erro = ResultadoExtracao(metodo="IRRECUPERAVEL", erros=[str(exc)])
        salvar_texto_e_registrar_log(
            caminho_pdf, caminho_txt, res_erro, ano_base, base_nome, cache_log, caminho_csv
        )
        return "IRRECUPERAVEL", res_erro

    except PdfIOError as exc:
        res_erro = ResultadoExtracao(metodo="ERRO", erros=[str(exc)])
        salvar_texto_e_registrar_log(
            caminho_pdf, caminho_txt, res_erro, ano_base, base_nome, cache_log, caminho_csv
        )
        return "ERRO_IO", res_erro

    except Exception as exc:
        res_erro = ResultadoExtracao(metodo="ERRO", erros=[f"Erro inesperado: {exc}"])
        salvar_texto_e_registrar_log(
            caminho_pdf, caminho_txt, res_erro, ano_base, base_nome, cache_log, caminho_csv
        )
        return "OUTRO_ERRO", res_erro


def imprimir_relatorio_final(stats: EstatisticasExtracao, ano_base: str) -> None:
    """Imprime o sumário estatístico detalhado de execução."""
    taxa_sucesso = (
        ((stats.sucesso_nativo + stats.sucesso_hibrido + stats.sucesso_ocr) / max(stats.processados_lote, 1))
        * 100
    )
    throughput = stats.processados_lote / max(stats.tempo_total_segundos, 0.001)

    print("\n" + "=" * 70)
    print(f"  RELATÓRIO CONSOLIDADO DE EXTRAÇÃO DE TEXTO — ANO-BASE {ano_base}")
    print("=" * 70)
    print(f"  Total de PDFs Encontrados em Disco:  {stats.total_encontrados:,}")
    print(f"  Pulos por Idempotência (Cache O(1)): {stats.pulos_idempotencia:,}")
    print(f"  Total Processado neste Lote:         {stats.processados_lote:,}")
    print("  " + "-" * 66)
    print(f"  ├── ✅ Sucesso Nativo (PyMuPDF):     {stats.sucesso_nativo:,}")
    print(f"  ├── 🔄 Sucesso Híbrido (Nativo+OCR): {stats.sucesso_hibrido:,}")
    print(f"  ├── 🔍 Sucesso OCR Completo:         {stats.sucesso_ocr:,}")
    print(f"  ├── ⚠️  Irrecuperáveis (<100 chars):  {stats.falhas_irrecuperaveis:,}")
    print(f"  ├── 🔒 Criptografados com Senha:     {stats.falhas_criptografados:,}")
    print(f"  ├── ❌ Arquivos Corrompidos / %PDF-: {stats.falhas_corrompidos:,}")
    print(f"  ├── 🌐 Falhas Persistentes de I/O:   {stats.falhas_io:,}")
    print(f"  └── ❓ Outras Exceções:              {stats.falhas_outras:,}")
    print("  " + "-" * 66)
    print(f"  Taxa de Aproveitamento Textual:      {taxa_sucesso:.2f}%")
    print(f"  Volume Total de Caracteres:          {stats.total_chars_extraidos:,} chars")
    print(f"  Tempo Total de Execução:             {stats.tempo_total_segundos:.2f} s")
    print(f"  Throughput Médio Global:             {throughput:.2f} PDFs/segundo")
    print("=" * 70 + "\n")


def executar_pipeline_extracao(
    ano_base: str = ANO_BASE,
    base_especifica: str | None = None,
    max_workers: int = 4,
    limite: int | None = None,
    dry_run: bool = False,
    forcar_ocr: bool = False,
) -> EstatisticasExtracao:
    """
    Orquestrador principal de lote.
    """
    inicio_global = time.perf_counter()
    stats = EstatisticasExtracao()

    pasta_dados_brutos = BASE_DRIVE / f"{ano_base}_Dados_brutos"
    pasta_textos = BASE_DRIVE / f"{ano_base}_Textos_extraidos"
    caminho_csv = pasta_textos / "log_extracao.csv"

    for _ in range(30):
        if BASE_DRIVE.exists():
            break
        time.sleep(2.0)

    inicializar_log_extracao_csv(caminho_csv)
    cache_log = carregar_pdfs_ja_processados(caminho_csv)
    _carregar_indice_cross_ano_txt()

    print(f"\n🚀 Iniciando Pipeline de Extração de Texto & OCR (Ano: {ano_base})")
    print(f"📂 Diretório de Entrada: {pasta_dados_brutos}")
    print(f"💾 Diretório de Saída:   {pasta_textos}")
    print(f"📊 Manifesto de Log:     {caminho_csv}")
    print(f"⚡ Cache O(1) Ativo:     {len(cache_log)} registros pré-carregados na memória.")

    if not pasta_dados_brutos.exists():
        logger.error(f"Diretório de dados brutos não encontrado: {pasta_dados_brutos}")
        return stats

    # Mapeia bases a processar
    if base_especifica:
        bases_alvo = [base_especifica.strip().lower()]
    else:
        bases_alvo = [d.name.lower() for d in pasta_dados_brutos.iterdir() if d.is_dir()]

    # Coleta arquivos candidatos
    candidatos_para_processar: list[tuple[Path, Path, str, str]] = []

    for base_nome in bases_alvo:
        pasta_base_in = pasta_dados_brutos / base_nome
        if not pasta_base_in.exists():
            continue

        pasta_base_out = obter_pasta_textos_base(base_nome, ano_base=ano_base)

        for pdf_path in pasta_base_in.glob("*.pdf"):
            if eh_ficha_sintetica_legada(pdf_path.name):
                continue
            stats.total_encontrados += 1
            chave = (str(ano_base).strip(), str(base_nome).strip().lower(), pdf_path.name.strip())

            # Trava de Idempotência O(1)
            if chave in cache_log and cache_log[chave] in ("OK", "OCR_PARCIAL", "IRRECUPERAVEL", "CORROMPIDO", "CRIPTOGRAFADO"):
                stats.pulos_idempotencia += 1
                continue

            candidatos_para_processar.append((pdf_path, pasta_base_out, ano_base, base_nome))

    if limite and limite > 0:
        candidatos_para_processar = candidatos_para_processar[:limite]

    print(f"\n📋 Candidatos a processar nesta execução: {len(candidatos_para_processar)} arquivos "
          f"({stats.pulos_idempotencia} pulados via cache O(1)).")

    if dry_run:
        print("\n🔍 MODO DRY-RUN: Nenhum arquivo será alterado.")
        for p, _, ano, base in candidatos_para_processar[:10]:
            print(f"  [DRY-RUN] Seria processado: {ano}/{base}/{p.name}")
        stats.tempo_total_segundos = round(time.perf_counter() - inicio_global, 2)
        imprimir_relatorio_final(stats, ano_base)
        return stats

    if not candidatos_para_processar:
        print("✅ Todos os PDFs deste escopo já foram processados! Nada a fazer.")
        stats.tempo_total_segundos = round(time.perf_counter() - inicio_global, 2)
        imprimir_relatorio_final(stats, ano_base)
        return stats

    # Execução concorrente Multi-Thread
    print(f"⚙️ Processando com pool de {max_workers} threads paralelas...\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                processar_um_arquivo,
                pdf_path,
                pasta_out,
                ano,
                base,
                cache_log,
                caminho_csv,
                forcar_ocr,
            ): pdf_path
            for (pdf_path, pasta_out, ano, base) in candidatos_para_processar
        }

        for future in as_completed(futures):
            pdf_orig = futures[future]
            stats.processados_lote += 1

            try:
                status_res, res = future.result()
                stats.total_chars_extraidos += res.total_chars

                if status_res == "SUCESSO_NATIVO":
                    stats.sucesso_nativo += 1
                elif status_res == "SUCESSO_HIBRIDO":
                    stats.sucesso_hibrido += 1
                elif status_res == "SUCESSO_OCR":
                    stats.sucesso_ocr += 1
                elif status_res == "CORROMPIDO":
                    stats.falhas_corrompidos += 1
                elif status_res == "CRIPTOGRAFADO":
                    stats.falhas_criptografados += 1
                elif status_res == "IRRECUPERAVEL":
                    stats.falhas_irrecuperaveis += 1
                elif status_res == "ERRO_IO":
                    stats.falhas_io += 1
                else:
                    stats.falhas_outras += 1

                # Log de progresso a cada 250 arquivos
                if stats.processados_lote % 250 == 0 or stats.processados_lote == len(candidatos_para_processar):
                    logger.info(
                        f"Progresso ({ano_base}): {stats.processados_lote}/{len(candidatos_para_processar)} "
                        f"({(stats.processados_lote / len(candidatos_para_processar)) * 100:.1f}%) | "
                        f"Último: {pdf_orig.name[:35]}... [{status_res}]"
                    )

            except Exception as exc:
                stats.falhas_outras += 1
                logger.error(f"Erro no worker para {pdf_orig.name}: {exc}")

    stats.tempo_total_segundos = round(time.perf_counter() - inicio_global, 2)
    imprimir_relatorio_final(stats, ano_base)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline de Extração de Texto (PDF -> TXT) e OCR com Resiliência e Idempotência."
    )
    parser.add_argument("--ano", type=str, default=ANO_BASE, help=f"Ano-base (ex: 2025, 2026). Padrão: {ANO_BASE}")
    parser.add_argument("--base", type=str, default=None, help="Filtrar por base específica (ex: dnit, caixa). Padrão: todas")
    parser.add_argument("--workers", type=int, default=4, help="Número de threads concorrentes. Padrão: 4")
    parser.add_argument("--limit", type=int, default=None, help="Limitar processamento a N arquivos para testes.")
    parser.add_argument("--dry-run", action="store_true", help="Apenas simula a lista de arquivos sem processar.")
    parser.add_argument("--force-ocr", action="store_true", help="Força OCR em todos os documentos.")

    args = parser.parse_args()

    executar_pipeline_extracao(
        ano_base=args.ano,
        base_especifica=args.base,
        max_workers=args.workers,
        limite=args.limit,
        dry_run=args.dry_run,
        forcar_ocr=args.force_ocr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
