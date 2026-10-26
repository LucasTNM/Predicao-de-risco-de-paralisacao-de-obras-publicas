# -*- coding: utf-8 -*-
"""Orquestrador multi-ano para higienização de textos extraídos.

Mantém os mesmos princípios do pipeline de extração: cache O(1), escrita antes
do manifesto CSV, retomada segura e isolamento de falhas por arquivo.
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
import sys
import threading
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import (
    ANOS_DISPONIVEIS,
    ANO_BASE,
    BASE_DRIVE,
    LIMIAR_SUJEIRA_LLM,
    logger,
)
from src.parsers.limpeza_llm import GeminiErro, limpar_texto_camada2
from src.parsers.limpeza_nlp import calcular_score_sujeira, limpar_texto_camada1
from src.utils import eh_ficha_sintetica_legada


COLUNAS_LOG_HIGIENIZACAO = [
    "timestamp",
    "ano_base",
    "base_de_dados",
    "nome_txt_entrada",
    "nome_txt_saida",
    "metodo_limpeza",
    "score_sujeira_antes",
    "score_sujeira_depois",
    "total_chars_antes",
    "total_chars_depois",
    "status",
    "observacoes",
]

_LOCK_LOG_HIGIENIZACAO = threading.Lock()
_INDICE_CROSS_LIMPO: dict[tuple[str, str], tuple[Path, dict[str, str]]] = {}


def _carregar_indice_cross_limpo(base_drive: Path) -> None:
    """Indexa textos limpos já processados em qualquer ano (2022–2026) para reuso O(1)."""
    if _INDICE_CROSS_LIMPO:
        return
    for ano in ANOS_DISPONIVEIS:
        pasta_saida = base_drive / f"{ano}_Textos_Limpos"
        caminho_csv = pasta_saida / "log_higienizacao.csv"
        if not caminho_csv.exists():
            continue
        try:
            with open(caminho_csv, "r", encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    status = (row.get("status") or "").strip().upper()
                    if status != "OK":
                        continue
                    base = (row.get("base_de_dados") or "").strip().lower()
                    nome_in = (row.get("nome_txt_entrada") or "").strip()
                    nome_out = (row.get("nome_txt_saida") or "").strip()
                    if not base or not nome_in or not nome_out or eh_ficha_sintetica_legada(nome_in):
                        continue
                    chave = (base, nome_in)
                    if chave not in _INDICE_CROSS_LIMPO:
                        caminho_txt = pasta_saida / base / nome_out
                        _INDICE_CROSS_LIMPO[chave] = (caminho_txt, row)
        except Exception as exc:
            logger.warning("Aviso ao carregar índice cross-ano de textos limpos (%s): %s", ano, exc)
    logger.info("Índice Cross-Ano de Textos Limpos: %d textos disponíveis para reuso O(1).", len(_INDICE_CROSS_LIMPO))


@dataclass
class ResultadoCamada1:
    """Resultado de leitura e limpeza determinística de um arquivo."""

    caminho_entrada: Path
    caminho_saida: Path
    ano_base: str
    base_nome: str
    texto_limpo: str = ""
    score_antes: float = 0.0
    score_camada1: float = 0.0
    total_chars_antes: int = 0
    erro: str = ""
    persistencia_tentada: bool = False
    persistido: bool = False


@dataclass
class EstatisticasHigienizacao:
    """Métricas consolidadas para uma execução de um ano-base."""

    total_encontrados: int = 0
    pulos_idempotencia: int = 0
    candidatos_camada2: int = 0
    processados_lote: int = 0
    sucesso_camada1: int = 0
    sucesso_camada2: int = 0
    camada2_indisponivel: int = 0
    falhas: int = 0
    total_chars_antes: int = 0
    total_chars_depois: int = 0
    tempo_total_segundos: float = 0.0
    observacoes: list[str] = field(default_factory=list)


def inicializar_log_higienizacao_csv(caminho_csv: Path) -> None:
    """Cria o manifesto de higienização com o cabeçalho canônico se necessário."""
    if caminho_csv.exists():
        return
    caminho_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_csv, "w", newline="", encoding="utf-8") as arquivo:
        csv.writer(arquivo).writerow(COLUNAS_LOG_HIGIENIZACAO)


def carregar_textos_ja_higienizados(caminho_csv: Path) -> dict[tuple[str, str, str], str]:
    """Carrega uma vez o cache ``(ano, base, txt) -> status`` do manifesto."""
    cache: dict[tuple[str, str, str], str] = {}

    try:
        if not caminho_csv.exists():
            return cache
        with open(caminho_csv, "r", encoding="utf-8", errors="replace") as arquivo:
            for linha in csv.DictReader(arquivo):
                ano = (linha.get("ano_base") or "").strip()
                base = (linha.get("base_de_dados") or "").strip().lower()
                nome = (linha.get("nome_txt_entrada") or "").strip()
                status = (linha.get("status") or "").strip().upper()
                if ano and base and nome:
                    cache[(ano, base, nome)] = status
    except (OSError, csv.Error) as exc:
        logger.warning("Não foi possível carregar cache de higienização (%s): %s", caminho_csv, exc)

    logger.info("Cache de Higienização: %s textos carregados em memória O(1).", len(cache))
    return cache


def salvar_texto_higienizado_e_registrar_log(
    *,
    caminho_entrada: Path,
    caminho_saida: Path,
    texto_limpo: str,
    ano_base: str,
    base_nome: str,
    metodo_limpeza: str,
    score_antes: float,
    score_depois: float,
    total_chars_antes: int,
    status: str,
    observacoes: str,
    cache_log: dict[tuple[str, str, str], str],
    caminho_csv: Path,
) -> bool:
    """Persiste texto e só então registra o manifesto, sob lock de concorrência."""
    chave = (str(ano_base).strip(), base_nome.strip().lower(), caminho_entrada.name.strip())

    try:
        for _ in range(30):
            if caminho_saida.parent.parent.exists():
                break
            time.sleep(2.0)
        caminho_saida.parent.mkdir(parents=True, exist_ok=True)
        temporario = caminho_saida.with_name(f".{caminho_saida.name}.{threading.get_ident()}.tmp")
        temporario.write_text(texto_limpo, encoding="utf-8")
        os.replace(temporario, caminho_saida)
    except OSError as exc:
        logger.error("Falha de I/O ao gravar texto higienizado (%s): %s", caminho_saida, exc)
        return False

    with _LOCK_LOG_HIGIENIZACAO:
        try:
            inicializar_log_higienizacao_csv(caminho_csv)
            row_values = [
                datetime.now().isoformat(),
                ano_base,
                base_nome.strip().lower(),
                caminho_entrada.name,
                caminho_saida.name,
                metodo_limpeza,
                f"{score_antes:.6f}",
                f"{score_depois:.6f}",
                total_chars_antes,
                len(texto_limpo),
                status,
                observacoes,
            ]
            with open(caminho_csv, "a", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow(row_values)
            cache_log[chave] = status.upper()
            if status.upper() == "OK" and not eh_ficha_sintetica_legada(caminho_entrada.name):
                chave_cross = (base_nome.strip().lower(), caminho_entrada.name.strip())
                if chave_cross not in _INDICE_CROSS_LIMPO:
                    _INDICE_CROSS_LIMPO[chave_cross] = (
                        caminho_saida,
                        dict(zip(COLUNAS_LOG_HIGIENIZACAO, [str(v) for v in row_values])),
                    )
            return True
        except (OSError, csv.Error) as exc:
            logger.error("Falha ao registrar manifesto de higienização para %s: %s", caminho_entrada.name, exc)
            return False


def _processar_camada1(
    caminho_entrada: Path,
    caminho_saida: Path,
    ano_base: str,
    base_nome: str,
    cache_log: dict[tuple[str, str, str], str],
    caminho_csv: Path,
    usar_reuso_cross: bool = False,
) -> ResultadoCamada1:
    """Worker concorrente: lê, limpa e persiste resultados que não usam LLM.

    A Camada 2 fica fora dos workers para manter chamadas Gemini sequenciais.
    Para os demais textos, a escrita atômica e o registro CSV continuam
    encapsulados na mesma operação, protegida pelo lock do manifesto.
    """
    resultado = ResultadoCamada1(caminho_entrada, caminho_saida, ano_base, base_nome)
    try:
        for _ in range(30):
            if caminho_entrada.parent.parent.exists():
                break
            time.sleep(2.0)

        chave_cross = (base_nome.strip().lower(), caminho_entrada.name.strip())
        if usar_reuso_cross and chave_cross in _INDICE_CROSS_LIMPO:
            caminho_origem, row_origem = _INDICE_CROSS_LIMPO[chave_cross]
            if caminho_origem.exists():
                try:
                    texto_reuso = caminho_origem.read_text(encoding="utf-8", errors="replace")
                    if len(texto_reuso.strip()) >= 100:
                        resultado.texto_limpo = texto_reuso
                        resultado.total_chars_antes = int(row_origem.get("total_chars_antes") or len(texto_reuso))
                        resultado.score_antes = float(row_origem.get("score_sujeira_antes") or 0.0)
                        resultado.score_camada1 = float(row_origem.get("score_sujeira_depois") or 0.0)
                        resultado.persistencia_tentada = True
                        resultado.persistido = salvar_texto_higienizado_e_registrar_log(
                            caminho_entrada=resultado.caminho_entrada,
                            caminho_saida=resultado.caminho_saida,
                            texto_limpo=resultado.texto_limpo,
                            ano_base=resultado.ano_base,
                            base_nome=resultado.base_nome,
                            metodo_limpeza=row_origem.get("metodo_limpeza") or "CAMADA1",
                            score_antes=resultado.score_antes,
                            score_depois=resultado.score_camada1,
                            total_chars_antes=resultado.total_chars_antes,
                            status="OK",
                            observacoes=f"REUSO_CROSS_ANO:{row_origem.get('ano_base', '')}",
                            cache_log=cache_log,
                            caminho_csv=caminho_csv,
                        )
                        if resultado.persistido:
                            return resultado
                except Exception:
                    pass

        texto_bruto = caminho_entrada.read_text(encoding="utf-8", errors="replace")
        resultado.total_chars_antes = len(texto_bruto)
        resultado.score_antes = calcular_score_sujeira(texto_bruto)
        resultado.texto_limpo, resultado.score_camada1 = limpar_texto_camada1(texto_bruto)
        if resultado.score_camada1 <= LIMIAR_SUJEIRA_LLM:
            resultado.persistencia_tentada = True
            resultado.persistido = salvar_texto_higienizado_e_registrar_log(
                caminho_entrada=resultado.caminho_entrada,
                caminho_saida=resultado.caminho_saida,
                texto_limpo=resultado.texto_limpo,
                ano_base=resultado.ano_base,
                base_nome=resultado.base_nome,
                metodo_limpeza="CAMADA1",
                score_antes=resultado.score_antes,
                score_depois=resultado.score_camada1,
                total_chars_antes=resultado.total_chars_antes,
                status="OK",
                observacoes="",
                cache_log=cache_log,
                caminho_csv=caminho_csv,
            )
            if not resultado.persistido:
                resultado.erro = "Falha ao persistir a saída da Camada 1."
    except OSError as exc:
        resultado.erro = f"Falha de I/O na leitura: {exc}"
    except Exception as exc:  # Uma falha isolada não interrompe o lote.
        resultado.erro = f"Falha inesperada na Camada 1: {exc}"
    return resultado


def _registrar_falha_leitura(
    resultado: ResultadoCamada1,
    cache_log: dict[tuple[str, str, str], str],
    caminho_csv: Path,
) -> None:
    """Registra falhas sem criar uma saída enganosa no diretório de textos limpos."""
    with _LOCK_LOG_HIGIENIZACAO:
        try:
            inicializar_log_higienizacao_csv(caminho_csv)
            with open(caminho_csv, "a", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow([
                    datetime.now().isoformat(),
                    resultado.ano_base,
                    resultado.base_nome.strip().lower(),
                    resultado.caminho_entrada.name,
                    "",
                    "CAMADA1",
                    "",
                    "",
                    0,
                    0,
                    "ERRO",
                    resultado.erro,
                ])
        except (OSError, csv.Error) as exc:
            logger.error("Falha ao registrar erro de higienização: %s", exc)


def imprimir_relatorio_final(stats: EstatisticasHigienizacao, ano_base: str) -> None:
    """Exibe indicadores suficientes para monitorar custo, qualidade e retomada."""
    throughput = stats.processados_lote / max(stats.tempo_total_segundos, 0.001)
    print("\n" + "=" * 70)
    print(f"  RELATÓRIO DE HIGIENIZAÇÃO NLP — ANO-BASE {ano_base}")
    print("=" * 70)
    print(f"  Textos encontrados:                 {stats.total_encontrados:,}")
    print(f"  Pulados por idempotência O(1):      {stats.pulos_idempotencia:,}")
    print(f"  Processados neste lote:              {stats.processados_lote:,}")
    print(f"  ├── Camada 1 concluída:              {stats.sucesso_camada1:,}")
    print(f"  ├── Camada 2 concluída:              {stats.sucesso_camada2:,}")
    print(f"  ├── Camada 2 indisponível/pulada:    {stats.camada2_indisponivel:,}")
    print(f"  └── Falhas:                          {stats.falhas:,}")
    print(f"  Candidatos à Camada 2:               {stats.candidatos_camada2:,}")
    print(f"  Caracteres antes/depois:              {stats.total_chars_antes:,} / {stats.total_chars_depois:,}")
    print(f"  Tempo total / throughput:             {stats.tempo_total_segundos:.2f}s / {throughput:.2f} textos/s")
    print("=" * 70 + "\n")


def _executar_ano(
    *,
    ano_base: str,
    base_especifica: str | None,
    max_workers: int,
    limite: int | None,
    dry_run: bool,
    skip_llm: bool,
    force: bool,
    base_drive: Path,
) -> EstatisticasHigienizacao:
    inicio = time.perf_counter()
    stats = EstatisticasHigienizacao()
    pasta_entrada = base_drive / f"{ano_base}_Textos_extraidos"
    pasta_saida = base_drive / f"{ano_base}_Textos_Limpos"
    caminho_csv = pasta_saida / "log_higienizacao.csv"

    print(f"\n🚀 Iniciando higienização (Ano: {ano_base})")
    print(f"📂 Entrada: {pasta_entrada}")
    print(f"💾 Saída:   {pasta_saida}")

    try:
        entrada_disponivel = pasta_entrada.is_dir()
    except OSError as exc:
        logger.error("Sem acesso ao diretório de textos extraídos (%s): %s", pasta_entrada, exc)
        stats.observacoes.append(f"Sem acesso ao diretório de entrada: {exc}")
        stats.tempo_total_segundos = round(time.perf_counter() - inicio, 2)
        return stats

    if not entrada_disponivel:
        logger.error("Diretório de textos extraídos não encontrado: %s", pasta_entrada)
        stats.tempo_total_segundos = round(time.perf_counter() - inicio, 2)
        return stats

    usar_reuso_cross = (base_drive == BASE_DRIVE) and not force
    if usar_reuso_cross:
        _carregar_indice_cross_limpo(base_drive)

    cache_log = carregar_textos_ja_higienizados(caminho_csv)
    if base_especifica:
        bases = [base_especifica.strip().lower()]
    else:
        try:
            bases = sorted(item.name.lower() for item in pasta_entrada.iterdir() if item.is_dir())
        except OSError as exc:
            logger.error("Não foi possível listar as bases em %s: %s", pasta_entrada, exc)
            stats.observacoes.append(f"Não foi possível listar as bases: {exc}")
            stats.tempo_total_segundos = round(time.perf_counter() - inicio, 2)
            return stats

    candidatos: list[tuple[Path, Path, str]] = []
    for base_nome in bases:
        origem_base = pasta_entrada / base_nome
        try:
            base_disponivel = origem_base.is_dir()
        except OSError as exc:
            logger.warning("Sem acesso à base %s no ano %s: %s", base_nome, ano_base, exc)
            continue
        if not base_disponivel:
            logger.warning("Base não encontrada no ano %s: %s", ano_base, base_nome)
            continue
        try:
            arquivos_txt = list(origem_base.glob("*.txt"))
        except OSError as exc:
            logger.warning("Não foi possível listar textos da base %s: %s", base_nome, exc)
            continue
        for caminho_entrada in arquivos_txt:
            if eh_ficha_sintetica_legada(caminho_entrada.name):
                continue
            stats.total_encontrados += 1
            chave = (str(ano_base), base_nome, caminho_entrada.name)
            if not force and cache_log.get(chave) == "OK":
                stats.pulos_idempotencia += 1
                continue
            candidatos.append((caminho_entrada, pasta_saida / base_nome / caminho_entrada.name, base_nome))

    if limite is not None and limite > 0:
        candidatos = candidatos[:limite]

    print(f"📋 Candidatos: {len(candidatos):,} | Pulados via cache: {stats.pulos_idempotencia:,}")
    if dry_run:
        print("🔍 MODO DRY-RUN: nenhum arquivo ou manifesto será criado.")
        for caminho, _, base in candidatos[:10]:
            print(f"  [DRY-RUN] {ano_base}/{base}/{caminho.name}")
        stats.tempo_total_segundos = round(time.perf_counter() - inicio, 2)
        imprimir_relatorio_final(stats, ano_base)
        return stats

    if not candidatos:
        stats.tempo_total_segundos = round(time.perf_counter() - inicio, 2)
        imprimir_relatorio_final(stats, ano_base)
        return stats

    print(f"⚙️ Camada 1 em pool de {max(1, max_workers)} workers; Camada 2 permanecerá sequencial.")
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futuros = {
            executor.submit(
                _processar_camada1,
                entrada,
                saida,
                ano_base,
                base,
                cache_log,
                caminho_csv,
                usar_reuso_cross,
            ): entrada
            for entrada, saida, base in candidatos
        }

        for futuro in as_completed(futuros):
            resultado = futuro.result()
            stats.processados_lote += 1

            if resultado.erro:
                stats.falhas += 1
                _registrar_falha_leitura(resultado, cache_log, caminho_csv)
            elif resultado.persistencia_tentada:
                if resultado.persistido:
                    stats.sucesso_camada1 += 1
                    stats.total_chars_antes += resultado.total_chars_antes
                    stats.total_chars_depois += len(resultado.texto_limpo)
                else:
                    stats.falhas += 1
            else:
                texto_final = resultado.texto_limpo
                metodo = "CAMADA1"
                observacoes = ""

                if resultado.score_camada1 > LIMIAR_SUJEIRA_LLM:
                    stats.candidatos_camada2 += 1
                    if skip_llm:
                        stats.camada2_indisponivel += 1
                        observacoes = "Camada 2 pulada por --skip-llm."
                    else:
                        try:
                            # Chamadas LLM ocorrem neste loop principal, nunca nas threads.
                            texto_final = limpar_texto_camada2(resultado.texto_limpo)
                            metodo = "CAMADA1+LLM"
                            stats.sucesso_camada2 += 1
                        except GeminiErro as exc:
                            stats.camada2_indisponivel += 1
                            observacoes = f"Camada 2 não aplicada: {exc}"
                            logger.warning("%s (%s)", observacoes, resultado.caminho_entrada.name)

                score_final = calcular_score_sujeira(texto_final)
                salvo = salvar_texto_higienizado_e_registrar_log(
                    caminho_entrada=resultado.caminho_entrada,
                    caminho_saida=resultado.caminho_saida,
                    texto_limpo=texto_final,
                    ano_base=resultado.ano_base,
                    base_nome=resultado.base_nome,
                    metodo_limpeza=metodo,
                    score_antes=resultado.score_antes,
                    score_depois=score_final,
                    total_chars_antes=resultado.total_chars_antes,
                    status="OK",
                    observacoes=observacoes,
                    cache_log=cache_log,
                    caminho_csv=caminho_csv,
                )
                if salvo:
                    stats.sucesso_camada1 += 1
                    stats.total_chars_antes += resultado.total_chars_antes
                    stats.total_chars_depois += len(texto_final)
                else:
                    stats.falhas += 1

            if stats.processados_lote % 250 == 0 or stats.processados_lote == len(candidatos):
                logger.info(
                    "Higienização %s/%s (%.1f%%) | último: %s",
                    stats.processados_lote,
                    len(candidatos),
                    (stats.processados_lote / len(candidatos)) * 100,
                    resultado.caminho_entrada.name,
                )

    stats.tempo_total_segundos = round(time.perf_counter() - inicio, 2)
    imprimir_relatorio_final(stats, ano_base)
    return stats


def executar_pipeline_higienizacao(
    ano_base: str | None = None,
    base_especifica: str | None = None,
    max_workers: int = 4,
    limite: int | None = None,
    dry_run: bool = False,
    skip_llm: bool = False,
    force: bool = False,
    base_drive: Path | None = None,
) -> dict[str, EstatisticasHigienizacao]:
    """Executa um ano indicado ou todos os anos disponíveis quando ``ano_base`` é nulo."""
    raiz_drive = base_drive if base_drive is not None else BASE_DRIVE
    anos = [str(ano_base)] if ano_base else ANOS_DISPONIVEIS
    return {
        ano: _executar_ano(
            ano_base=ano,
            base_especifica=base_especifica,
            max_workers=max_workers,
            limite=limite,
            dry_run=dry_run,
            skip_llm=skip_llm,
            force=force,
            base_drive=raiz_drive,
        )
        for ano in anos
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Higienização NLP multi-ano de textos extraídos de PDFs.")
    parser.add_argument("--ano", default=None, help="Ano-base (2025 ou 2026). Sem opção, processa ambos.")
    parser.add_argument("--base", default=None, help="Filtra uma base específica.")
    parser.add_argument("--workers", type=int, default=4, help="Workers apenas para a Camada 1.")
    parser.add_argument("--limit", type=int, default=None, help="Limita o total de textos do lote.")
    parser.add_argument("--dry-run", action="store_true", help="Lista candidatos sem gravar arquivos.")
    parser.add_argument("--skip-llm", action="store_true", help="Desativa a Camada 2 mesmo acima do limiar.")
    parser.add_argument("--force", action="store_true", help="Reprocessa textos mesmo quando houver checkpoint OK.")
    args = parser.parse_args()
    executar_pipeline_higienizacao(
        ano_base=args.ano,
        base_especifica=args.base,
        max_workers=args.workers,
        limite=args.limit,
        dry_run=args.dry_run,
        skip_llm=args.skip_llm,
        force=args.force,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
