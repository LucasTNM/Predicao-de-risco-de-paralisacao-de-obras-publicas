"""Orquestracao dos Cards 6/7; relatorios locais, corpus de origem somente leitura."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import time

from src.config import ANOS_DISPONIVEIS, BASE_DRIVE, ROOT_DIR, LOGS_DIR
from src.database.preflight import audit_sources, file_hash


def source_fingerprints(root, drive, year):
    """Identifica exatamente as fontes tabulares lidas, sem copiar seu conteudo."""
    paths = {
        'planilha': Path(root) / f'data_{year}.xlsx',
        'coleta': Path(drive) / f'{year}_Dados_brutos/log_coleta.csv',
        'extracao': Path(drive) / f'{year}_Textos_extraidos/log_extracao.csv',
        'higienizacao': Path(drive) / f'{year}_Textos_Limpos/log_higienizacao.csv',
    }
    return {name: {'arquivo': str(path), 'sha256': file_hash(path)}
            for name, path in paths.items()}


def save_report(path, report):
    """Publica JSON completo por replace atomico; falha persistente e explicita."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(5):
            try:
                temporary.replace(path)
                return
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_load(year=None, base=None, limit=None, dry_run=False, force=False,
             root=ROOT_DIR, drive=BASE_DRIVE, *, exclude_quarantine=False):
    if year and str(year) not in ANOS_DISPONIVEIS:
        raise ValueError('Ano de carga deve ser 2025 ou 2026.')
    if limit is not None and limit < 1:
        raise ValueError('Limite deve ser positivo.')
    base = base.strip().lower() if base else None
    years = [int(year)] if year else [int(y) for y in ANOS_DISPONIVEIS]
    tag = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    report_path = LOGS_DIR / f'sprint3_{tag}.json'
    report = {'inicio': tag, 'dry_run': dry_run, 'limit_por_base': limit, 'base': base,
              'status': 'EM_EXECUCAO', 'prontidao': 'NAO_CONCLUIDO',
              'excluir_quarentena': exclude_quarantine,
              'anos_solicitados': years, 'anos': [], 'resultados': {}, 'falhas_carga': [],
              'codigo_sha256': {name: file_hash(ROOT_DIR / name) for name in (
                  'src/database/run_load.py', 'src/database/preflight.py',
                  'src/database/load_documentos.py', 'src/parsers/chunker.py',
                  'src/config.py', 'sql/001_sprint3_esquema_estrela.sql')}}

    def save():
        save_report(report_path, report)

    conn = None
    try:
        save()
        print(f'Relatorio: {report_path}', flush=True)
        audits = []
        for y in years:
            report['progresso'] = {'ano': y, 'verificados': 0, 'total': None}
            save()
            print(f'[preflight] Conferindo fontes de {y}...', flush=True)
            before = source_fingerprints(root, drive, y)

            def progress(done, total):
                report['progresso'] = {'ano': y, 'verificados': done, 'total': total}
                save()
                print(f'[preflight] {y}: {done}/{total} fontes fisicas verificadas.', flush=True)

            audit = audit_sources(Path(root), Path(drive), y, base, progress=progress)
            audits.append(audit)
            summary = audit.summary()
            after = source_fingerprints(root, drive, y)
            summary.update(fontes_antes=before, fontes_depois=after,
                           fontes_estaveis=before == after)
            summary['prontidao'] = ('BLOQUEADO' if before != after or not audit.documents or
                                    any(i['estado'] == 'quarentena' for i in audit.issues)
                                    else 'APTO_COM_EXCLUSOES' if audit.issues else 'APTO')
            inventory_path = report_path.with_name(f'{report_path.stem}_{y}_elegiveis.json')
            save_report(inventory_path, [
                {'ano': d.year, 'base': d.base, 'pdf': d.pdf, 'txt': d.txt,
                 'obras': d.works, 'sha256_pdf': d.extraction['sha256_pdf'],
                 'sha256_txt': d.text_hash} for d in audit.documents])
            summary['inventario_elegiveis'] = {'arquivo': str(inventory_path),
                'sha256': file_hash(inventory_path), 'documentos': len(audit.documents)}
            report['anos'].append(summary)
            save()
            print(json.dumps({k: summary[k] for k in ('ano', 'obras', 'textos_manifestados',
                  'elegiveis', 'ocorrencias', 'prontidao')}, ensure_ascii=False), flush=True)
            if before != after:
                raise ValueError(f'fontes tabulares alteradas durante auditoria de {y}; repetir preflight.')
        report['prontidao'] = ('BLOQUEADO' if any(a['prontidao'] == 'BLOQUEADO' for a in report['anos'])
                              else 'APTO_COM_EXCLUSOES' if any(a['ocorrencias'] for a in report['anos'])
                              else 'APTO')
        if dry_run:
            report['status'] = 'PREFLIGHT'
            report['fim'] = datetime.now().astimezone().isoformat()
            save()
            print(f'Relatorio: {report_path}', flush=True)
            return report
        if not any(a.documents for a in audits):
            raise ValueError('Preflight sem documentos elegiveis; revisar fontes antes da carga.')
        if any(i['estado'] == 'quarentena' for a in audits for i in a.issues) and not exclude_quarantine:
            raise ValueError('Preflight com quarentena; revisar destinacao e usar --excluir-quarentena '
                             'somente para carregar os documentos elegiveis.')
        from src.database.connection import connect
        from src.database.schema import validate_schema
        from src.database.load_obras import load_works
        from src.database.load_documentos import load_document, DocumentError
        from src.database.validation import validate_data
        from src.parsers.chunker import load_chunker

        chunker = load_chunker()
        report['chunk_config'] = chunker.config
        conn = connect()
        validate_schema(conn)
        results = Counter()
        started = time.monotonic()
        for audit in audits:
            facts = load_works(conn, audit)
            print(f'[carga] {audit.year}: {len(facts)} obras/fatos reconciliados.', flush=True)
            selected = Counter()
            for doc in audit.documents:
                if limit and selected[doc.base] >= limit:
                    continue
                selected[doc.base] += 1
                try:
                    result = load_document(conn, doc, Path(drive), facts, chunker, force)
                    results[result['estado']] += 1
                    results['ocorrencias_chunks'] += result['chunks']
                except (DocumentError, OSError, UnicodeError, KeyError, ValueError) as exc:
                    results['falhas'] += 1
                    report['falhas_carga'].append({'ano': doc.year, 'base': doc.base,
                        'txt': doc.txt, 'motivo': str(exc), 'tipo': type(exc).__name__})
                processed = results['carregado'] + results['reutilizado'] + results['falhas']
                if processed % 100 == 0:
                    report['resultados'] = dict(results)
                    save()
                    print(f'[carga] {processed} documentos, {results["falhas"]} falhas, {time.monotonic()-started:.0f}s', flush=True)
        report['resultados'] = dict(results)
        report['validacao'] = validate_data(conn)
        pending = any(i['estado'] == 'quarentena' for a in audits for i in a.issues)
        report['status'] = 'PARCIAL' if (pending or results['falhas'] or limit or not report['validacao']['valido']) else 'CONCLUIDO'
        report['fim'] = datetime.now().astimezone().isoformat()
        save()
        print(json.dumps({'status': report['status'], 'resultados': report['resultados'],
                          'validacao': report['validacao'], 'relatorio': str(report_path)}, ensure_ascii=False), flush=True)
        return report
    except BaseException as exc:
        report['status'] = 'INTERROMPIDO'
        report['prontidao'] = 'BLOQUEADO'
        report['fim'] = datetime.now().astimezone().isoformat()
        # Nao incluir mensagens de drivers: podem conter parametros/credenciais.
        report['erro_fatal'] = type(exc).__name__
        try:
            save()
        except OSError:
            exc.add_note('Tambem nao foi possivel persistir o relatorio de interrupcao.')
        raise
    finally:
        if conn is not None:
            conn.close()
