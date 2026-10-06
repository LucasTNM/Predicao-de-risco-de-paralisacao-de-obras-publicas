"""Start/reuse Docker Desktop and wait for the project's PostgreSQL."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.docker_runtime import DockerRuntimeError, ensure_postgres


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout',type=float,default=240)
    args=parser.parse_args()
    try:
        result=ensure_postgres(ROOT,timeout=args.timeout)
    except (DockerRuntimeError,ValueError) as error:
        print(f'Falha de preparacao: {error}',file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
