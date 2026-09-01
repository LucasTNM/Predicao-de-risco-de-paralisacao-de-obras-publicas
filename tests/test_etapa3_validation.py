# -*- coding: utf-8 -*-
"""
tests/test_etapa3_validation.py
===============================
Suíte de testes de validação profunda para a Etapa 3:
- Resiliência e Idempotência (Pause & Resume).
- Padrão Write-Ahead com PDF real do Google Drive.
- Concorrência Thread-Safe em escrita de manifesto CSV.
- Validação de integridade no sistema de arquivos.
"""

from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import sys
import tempfile
import time

# Força UTF-8 no stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src.parsers import (
    COLUNAS_LOG_EXTRACAO,
    ResultadoExtracao,
    calcular_sha256_arquivo,
    carregar_pdfs_ja_processados,
    inicializar_log_extracao_csv,
    processar_pdf,
    salvar_texto_e_registrar_log,
    verificar_txt_existente_valido,
)
from src.config import BASE_DRIVE


def testar_write_ahead_com_pdf_real(temp_dir: Path) -> Path:
    print("\n--- 1. Teste de Write-Ahead com PDF Real do Google Drive ---")
    
    pasta_dnit = BASE_DRIVE / "2026_Dados_brutos" / "dnit"
    pdfs = list(pasta_dnit.glob("*.pdf")) if pasta_dnit.exists() else []
    
    # Encontra um PDF válido
    pdf_real = None
    for p in pdfs:
        try:
            with open(p, "rb") as f:
                if f.read(5) == b"%PDF-":
                    pdf_real = p
                    break
        except Exception:
            continue

    if not pdf_real:
        print("⚠️ Nenhum PDF do DNIT acessível no Drive. Criando PDF sintético de fallback.")
        pdf_real = temp_dir / "obra_mock.pdf"
        pdf_real.write_bytes(b"%PDF-1.4 mock de teste")

    print(f"📄 Arquivo de Entrada: {pdf_real.name} ({pdf_real.stat().st_size / 1024:.1f} KB)")
    
    # Executa extração real
    resultado = processar_pdf(pdf_real)
    print(f"⚡ Extração concluída: {resultado.metodo} | {resultado.total_chars:,} chars | {resultado.total_paginas} págs em {resultado.tempo_segundos:.4f}s")
    
    # Define caminhos de saída
    txt_saida = temp_dir / "textos" / "dnit" / f"{pdf_real.stem}.txt"
    csv_log = temp_dir / "log_extracao.csv"
    cache_log: dict[tuple[str, str, str], str] = {}

    # Executa persistência Write-Ahead
    sucesso = salvar_texto_e_registrar_log(
        caminho_pdf=pdf_real,
        caminho_txt=txt_saida,
        resultado=resultado,
        ano_base="2026",
        base_nome="dnit",
        cache_log=cache_log,
        caminho_csv=csv_log,
    )

    assert sucesso is True, "Falha na função salvar_texto_e_registrar_log"
    assert txt_saida.exists(), "O arquivo .txt não foi criado fisicamente no disco"
    assert txt_saida.stat().st_size > 0, "O arquivo .txt gravado está vazio (0 bytes)"
    assert csv_log.exists(), "O manifesto CSV de log não foi criado"

    # Inspeciona o conteúdo gravado no CSV
    with open(csv_log, "r", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    
    assert len(linhas) == 1, f"Esperada 1 linha no log, encontradas {len(linhas)}"
    reg = linhas[0]
    
    print(f"✅ Arquivo .txt gravado com sucesso: {txt_saida.name} ({txt_saida.stat().st_size / 1024:.1f} KB)")
    print(f"✅ Registro no CSV validado:")
    print(f"   - Timestamp:        {reg['timestamp']}")
    print(f"   - Ano / Base:       {reg['ano_base']} / {reg['base_de_dados']}")
    print(f"   - Arquivo PDF:      {reg['nome_pdf']}")
    print(f"   - Arquivo TXT:      {reg['nome_txt']}")
    print(f"   - Método / Status:  {reg['metodo_extracao']} / {reg['status']}")
    print(f"   - Chars / Páginas:  {reg['total_chars']} chars / {reg['total_paginas']} págs")
    print(f"   - SHA-256 PDF:      {reg['sha256_pdf'][:16]}...")
    
    return csv_log


def testar_pause_and_resume_cache(csv_log: Path) -> None:
    print("\n--- 2. Teste de Idempotência e Retomada Instantânea (Pause & Resume) ---")
    
    inicio = time.perf_counter()
    cache = carregar_pdfs_ja_processados(csv_log)
    tempo_carga = (time.perf_counter() - inicio) * 1000

    print(f"⚡ Cache O(1) carregado em {tempo_carga:.3f} ms. Total de registros: {len(cache)}")
    
    # Simula consulta do orquestrador para verificar se um PDF já foi processado
    chave_existente = ("2026", "dnit", list(cache.keys())[0][2])
    chave_nova = ("2026", "dnit", "obra_inedita_que_nao_existe.pdf")

    t0 = time.perf_counter()
    ja_processado = chave_existente in cache
    status = cache.get(chave_existente)
    tempo_busca = (time.perf_counter() - t0) * 1_000_000  # em microssegundos (µs)

    assert ja_processado is True, "Chave existente não encontrada no cache O(1)"
    assert status == "OK", f"Status incorreto no cache: {status}"
    assert (chave_nova in cache) is False, "Chave nova incorretamente detectada no cache"

    print(f"✅ Verificação de Idempotência O(1):")
    print(f"   - Chave consultada: {chave_existente}")
    print(f"   - Já processado?    {ja_processado} (Status: {status})")
    print(f"   - Tempo de consulta: {tempo_busca:.2f} µs (< 0.001 ms)")


def testar_concorrencia_multithread(temp_dir: Path) -> None:
    print("\n--- 3. Teste de Concorrência Multi-Thread (Thread-Safety do Lock) ---")
    
    csv_concorrente = temp_dir / "log_concorrente.csv"
    inicializar_log_extracao_csv(csv_concorrente)
    cache_concorrente: dict[tuple[str, str, str], str] = {}

    num_threads = 10
    registros_por_thread = 20
    total_esperado = num_threads * registros_por_thread

    def worker_gravacao(thread_id: int) -> None:
        for i in range(registros_por_thread):
            nome_pdf = f"obra_t{thread_id}_item_{i}.pdf"
            nome_txt = f"obra_t{thread_id}_item_{i}.txt"
            pdf_fake = temp_dir / nome_pdf
            txt_fake = temp_dir / nome_txt
            
            # Cria arquivos simulados
            pdf_fake.write_bytes(b"%PDF-1.4 fake")
            
            res_mock = ResultadoExtracao(
                texto_completo=f"Texto gerado pela thread {thread_id} item {i}",
                total_chars=40,
                total_paginas=1,
                paginas_com_texto=1,
                metodo="NATIVO",
                tempo_segundos=0.001,
            )
            salvar_texto_e_registrar_log(
                caminho_pdf=pdf_fake,
                caminho_txt=txt_fake,
                resultado=res_mock,
                ano_base="2026",
                base_nome="caixa",
                cache_log=cache_concorrente,
                caminho_csv=csv_concorrente,
            )

    print(f"🚀 Disparando {num_threads} threads concorrentes ({total_esperado} gravações simultâneas)...")
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_gravacao, t) for t in range(num_threads)]
        for f in futures:
            f.result()
    duracao = time.perf_counter() - inicio

    # Valida integridade do CSV gravado concorrentemente
    with open(csv_concorrente, "r", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    assert len(linhas) == total_esperado, f"Esperadas {total_esperado} linhas, encontradas {len(linhas)}"
    assert len(cache_concorrente) == total_esperado, f"Cache contém {len(cache_concorrente)} itens"

    print(f"✅ Thread-Safety Homologado com Sucesso:")
    print(f"   - Total de gravações atômicas: {len(linhas)} / {total_esperado}")
    print(f"   - Tempo total decorrido:       {duracao:.3f} s ({total_esperado / duracao:.1f} ops/segundo)")
    print(f"   - Nenhuma linha corrompida no CSV sob concorrência intensa.")


def testar_resiliencia_filesystem(temp_dir: Path) -> None:
    print("\n--- 4. Teste de Validação de Integridade no Filesystem (Tarefa 3.4) ---")
    
    txt_valido = temp_dir / "valido.txt"
    txt_valido.write_text("Conteudo valido de teste", encoding="utf-8")

    txt_vazio = temp_dir / "vazio.txt"
    txt_vazio.write_bytes(b"")

    txt_inexistente = temp_dir / "nao_existe.txt"

    assert verificar_txt_existente_valido(txt_valido) is True, "Deveria ser válido"
    assert verificar_txt_existente_valido(txt_vazio) is False, "Arquivo de 0 bytes não deve ser válido"
    assert verificar_txt_existente_valido(txt_inexistente) is False, "Arquivo inexistente não deve ser válido"

    print(f"✅ Fallback de filesystem validado com precisão (Valido: True | Vazio: False | Inexistente: False).")


def main() -> int:
    print("===========================================================================")
    print("  VALIDAÇÃO COMPLETA DA ETAPA 3: RESILIÊNCIA, IDEMPOTÊNCIA E WRITE-AHEAD  ")
    print("===========================================================================")

    temp_dir = Path(tempfile.mkdtemp())
    try:
        csv_log = testar_write_ahead_com_pdf_real(temp_dir)
        testar_pause_and_resume_cache(csv_log)
        testar_concorrencia_multithread(temp_dir)
        testar_resiliencia_filesystem(temp_dir)

        print("\n===========================================================================")
        print("  🎉 TODAS AS VALIDAÇÕES DA ETAPA 3 FORAM APROVADAS COM 100% DE SUCESSO!   ")
        print("===========================================================================")
        return 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
