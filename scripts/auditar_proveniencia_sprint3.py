"""Confere a cadeia fisica dos documentos do piloto sem homologar sua origem."""
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg.rows import dict_row
from src.database.connection import connect
from src.database.run_load import save_report


def inspect_document(row, root):
    failures, evidence = [], {}
    year = row['ano_base']
    for kind, directory in [('pdf', f'{year}_Dados_brutos'), ('txt', f'{year}_Textos_Limpos')]:
        base = (root / directory).resolve()
        path = (base / row[f'caminho_{kind}_relativo']).resolve()
        expected = row[f'sha256_{kind}']
        actual = None
        if not path.is_relative_to(base):
            failures.append('caminho_invalido')
        elif not path.is_file():
            failures.append(f'{kind}_ausente')
        else:
            with path.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != expected:
                failures.append(f'{kind}_hash_divergente')
        evidence[kind] = dict(caminho=str(path), esperado=expected, observado=actual)
    meta = row['metadados'] or {}
    collection = meta.get('coleta', [])
    if not collection or any(item.get('status_validacao') not in {'VALIDADO', 'VALIDADO_COM_RESSALVAS'} for item in collection):
        failures.append('coleta_nao_aceita')
    for stage in ('extracao', 'higienizacao'):
        if meta.get(stage, {}).get('status') != 'OK':
            failures.append(stage + '_nao_ok')
    return dict(id_documento=row['id_documento'], ano_base=year,
        origem_registrada=row['origem_documento'], homologacao_original=False,
        cadeia_integra=not failures, falhas=failures, arquivos=evidence,
        coleta=collection, extracao=meta.get('extracao'), higienizacao=meta.get('higienizacao'),
        observacao='Integridade e aceite da coleta nao homologam automaticamente origem original.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('G:/Meu Drive/TCC_DOCUMENTOS'))
    args = parser.parse_args()
    with connect() as conn:
        conn.read_only = True
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute('''SELECT d.* FROM tcc.dim_documento d WHERE EXISTS (
                SELECT 1 FROM tcc.ponte_documento_embedding p JOIN tcc.dim_embedding e USING(id_embedding)
                WHERE p.id_documento=d.id_documento AND e.embedding IS NOT NULL) ORDER BY d.id_documento''')
            rows = cursor.fetchall()
    results = [inspect_document(row, args.root) for row in rows]
    report = dict(documentos=len(results), integros=sum(r['cadeia_integra'] for r in results),
                  homologacao_original=False, resultados=results)
    path = Path('logs') / ('sprint3_proveniencia_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    save_report(path, report)
    print(path, report['documentos'], report['integros'])
    return 0 if report['integros'] == report['documentos'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
