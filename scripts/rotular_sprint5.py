"""Rotulagem historica 0-3 conforme PCC; simulacao padrao, escrita com --write."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.database.connection import connect
from src.database.labeling import apply_labels, audit_labels, inventory, preservation_fingerprints
from src.database.schema import validate_schema
from src.labeling.recovery import recovery_report
from src.labeling.policy import canonical


@contextmanager
def reserve_output(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + '.lock')
    handle = lock.open('x', encoding='utf-8')
    try:
        with handle:
            if path.exists():
                raise ValueError('output_ja_existe_use_outro_nome')
            yield
    finally:
        lock.unlink(missing_ok=True)


def publish(path, result):
    # Hard-link publica o arquivo completo atomicamente e nunca substitui destino.
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, suffix='.tmp') as f:
        temp = Path(f.name)
        f.write((canonical(result) + '\n').encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    try:
        os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def load_reviews(path):
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict) or not isinstance(value.get('decisoes'), list):
        raise ValueError('input_exige_objeto_com_decisoes')
    for item in value['decisoes']:
        if isinstance(item, dict) and isinstance(item.get('evidencia'), dict):
            name = item['evidencia'].get('caminho')
            if isinstance(name, str) and name.strip():
                item['evidencia']['caminho'] = str((path.parent / name).resolve())
    return value['decisoes']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('inventariar', 'aplicar', 'revisar', 'auditar', 'recuperar'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--output', type=Path, required=True)
        if name in ('aplicar', 'revisar'):
            cmd.add_argument('--write', action='store_true')
        if name == 'revisar':
            cmd.add_argument('--input', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with reserve_output(args.output), connect() as conn:
            validate_schema(conn)
            if args.command in ('inventariar', 'recuperar'):
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    result = inventory(conn) if args.command == 'inventariar' else recovery_report(conn)
            elif args.command == 'auditar':
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    result = audit_labels(conn)
                    result['fingerprints'] = preservation_fingerprints(conn)
            else:
                reviews = load_reviews(args.input.resolve()) if args.command == 'revisar' else None
                result = apply_labels(conn, write=args.write, reviews=reviews)
            result['executado_em'] = datetime.now(timezone.utc).isoformat()
            publish(args.output, result)
        summary = {k: v for k,v in result.items() if k in
                   ('total','por_ano','valido','modo','examinados','propostos','atualizados','reutilizados','preservacao_verificada')}
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if result.get('valido', True) else 2
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'Falha de rotulagem: {exc}', file=sys.stderr)
        return 2
    except Exception as exc:
        # Erros SQL podem conter dados/DSN: nao expor mensagem bruta.
        print(f'Falha de rotulagem ({type(exc).__name__}); lote nao confirmado ou relatorio pendente. '
              'Confira o banco antes de repetir.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
