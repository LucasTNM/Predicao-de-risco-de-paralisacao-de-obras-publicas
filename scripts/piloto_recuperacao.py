"""Execute the bounded recovery pilot without changing PostgreSQL."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from src.labeling.pilot import prepare, audit_legacy, dataset_registry, summarize, apply_identity_reviews
from src.labeling.pilot_sources import PublicClient, atomic_json, read_json, crosswalk_rows, collect_case
from src.labeling.policy import digest


def implementation_hash():
    import hashlib
    files=('scripts/piloto_recuperacao.py','src/labeling/pilot.py',
           'src/labeling/pilot_sources.py','src/labeling/policy.py',
           'src/labeling/policy_v2.py','src/labeling/recovery.py')
    return digest({name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files})


def check_resume(result, manifest_hash, code_hash):
    if result.get('manifesto_sha256')!=manifest_hash:
        raise ValueError('resultado_de_outro_manifesto')
    if result.get('implementacao_sha256')!=code_hash:
        raise ValueError('implementacao_alterada_usar_coletar_reprocessar')
    import hashlib
    for attempt in result.get('tentativas',[]):
        if hashlib.sha256(Path(attempt['arquivo']).read_bytes()).hexdigest()!=attempt['sha256']:
            raise ValueError('resposta_alterada')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('preparar','coletar','relatar'))
    parser.add_argument('--output',type=Path,default=ROOT/'logs/piloto_recuperacao')
    parser.add_argument('--reprocessar',action='store_true',
                        help='Recalcular resultados com respostas cacheadas e registrar nova implementação.')
    args=parser.parse_args()
    output=args.output.resolve()
    manifest_path=output/'manifesto_piloto.json'
    if args.command=='preparar':
        from src.database.connection import connect
        from src.config import PASTA_TEXTOS_LIMPOS
        with connect() as conn:
            conn.read_only=True
            conn.isolation_level=__import__('psycopg').IsolationLevel.REPEATABLE_READ
            with conn.transaction():
                manifest,rows,audit=prepare(conn)
        # Normalize dates/decimals exactly as persisted before comparing resumes.
        import json
        manifest=json.loads(json.dumps(manifest,default=str))
        if manifest_path.exists() and digest(read_json(manifest_path))!=digest(manifest):
            raise ValueError('manifesto_existente_divergente_usar_outro_diretorio')
        atomic_json(manifest_path,manifest)
        atomic_json(output/'populacao.json',rows)
        atomic_json(output/'auditoria_banco_antes.json',audit)
        atomic_json(output/'auditoria_legados.json',audit_legacy(manifest['casos'],PASTA_TEXTOS_LIMPOS))
        print('Manifesto:22 legados +60 novos; banco somente leitura.')
        return
    manifest=read_json(manifest_path)
    signature=digest(manifest)
    code_hash=implementation_hash()
    if args.command=='coletar':
        client=PublicClient(output/'respostas')
        crosswalk=crosswalk_rows(client)
        atomic_json(output/'crosswalk_proveniencia.json',client.attempts)
        for case in manifest['casos']:
            path=output/'resultados'/f"{case['id_fato']}.json"
            if path.exists():
                prior=read_json(path)
                if prior.get('manifesto_sha256')!=signature:
                    raise ValueError('resultado_de_outro_manifesto')
                if not args.reprocessar:
                    check_resume(prior,signature,code_hash)
                    print(f"{case['id_fato']}: reuso",flush=True)
                    continue
                # Preserve the preceding derived result before publishing a new one.
                atomic_json(output/'historico_resultados'/f"{case['id_fato']}_{digest(prior)}.json",prior)
            if case['coorte']=='legado':
                result=dict(id_fato=case['id_fato'],id_tcu=case['id_tcu'],base_de_dados=case['base_de_dados'],
                            coorte='legado',status='quarentena_identidade_nao_confirmada',
                            consulta_especifica=False,identidade_confirmada=False,
                            candidatos_historicos=[],causa_homologada=False,label_risco=None,
                            auditoria='auditoria_legados.json',segundos=0)
            else:
                result=collect_case(case,client,crosswalk)
            result['manifesto_sha256']=signature
            result['implementacao_sha256']=code_hash
            atomic_json(path,result)
            print(f"{case['id_fato']} {case['base_de_dados']}: {result['status']}",flush=True)
    else:
        results=[read_json(output/'resultados'/f"{case['id_fato']}.json") for case in manifest['casos']]
        for result in results:
            check_resume(result,signature,code_hash)
        audits=read_json(output/'auditoria_legados.json')
        reviews_path=output/'revisoes_identidade.json'
        if reviews_path.exists():
            results,audits=apply_identity_reviews(results,audits,read_json(reviews_path))
        atomic_json(output/'quarentena_vinculos.json',audits)
        atomic_json(output/'resultados_piloto.json',results)
        atomic_json(output/'resumo.json',summarize(results))
        dataset=dataset_registry(read_json(output/'populacao.json'))
        quarantined={a['id_fato']:[d['id_documento'] for d in a['documentos']] for a in audits}
        for row in dataset:
            row['documentos_em_quarentena']=quarantined.get(row['id_fato'],[])
        atomic_json(output/'dataset_acompanhamento.json',dataset)
        print(f'{len(results)} resultados consolidados; nenhum rotulo atribuido.')


if __name__=='__main__':
    main()
