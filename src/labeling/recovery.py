"""Prepara recuperacao de causa na propria obra; nao infere classe por palavra."""
from collections import Counter, defaultdict

from psycopg.rows import dict_row

from src.labeling.policy import fingerprint, in_scope, normalize
from src.labeling.policy_v2 import missing_cause

# Localizadores de trechos para revisao, sem mapeamento automatico de classe.
LOCATORS = ('paralis', 'abandono', 'rescis', 'rescind', 'contrapartida',
            'falta de pagamento', 'atraso no pagamento', 'deficiencia',
            'licenciamento', 'falencia', 'desequilibrio', 'interrupcao', 'suspensao')


def eligible(row):
    return in_scope(row) and normalize(row['situacao']) == 'paralisada' and missing_cause(row['causa_paralisacao'])


def build_recovery(rows, documents, chunks):
    grouped_docs, best = defaultdict(dict), defaultdict(list)
    for doc in documents:
        grouped_docs[doc['id_fato']][doc['id_documento']] = doc
    for chunk in chunks:
        fact, doc_id = chunk['id_fato'], chunk['id_documento']
        doc = grouped_docs[fact].get(doc_id)
        if not doc or doc['origem_documento'] not in ('original', 'nao_confirmada'):
            continue
        normalized = normalize(chunk['conteudo_chunk'])
        hits = [term for term in LOCATORS if term in normalized]
        if not hits:
            continue
        candidate = {**chunk, 'localizadores': hits,
                     'origem_documento': doc['origem_documento'],
                     'aviso': 'Candidato para leitura; conferir obra, data, negacoes e causa factual.'}
        best[fact].append(candidate)
        best[fact].sort(key=lambda c: (-len(c['localizadores']), c['id_documento'], c['posicao_chunk'], c['id_embedding']))
        del best[fact][3:]
    result, counts = [], Counter()
    for row in rows:
        if not eligible(row):
            continue
        docs = sorted(grouped_docs[row['id_fato']].values(), key=lambda d:d['id_documento'])
        origins = {d['origem_documento'] for d in docs}
        if 'original' in origins:
            action = 'revisar_documento_original_vinculo_data_e_causa'
        elif 'nao_confirmada' in origins:
            action = 'confirmar_vinculo_origem_data_e_causa'
        elif docs:
            action = 'coletar_original_so_ficha_sintetica'
        else:
            action = 'coletar_original_sem_documentos'
        counts[action] += 1
        result.append(dict(id_fato=row['id_fato'], base_de_dados=row['base_de_dados'],
                           id_tcu=row['id_tcu'], data_base=str(row['data_base']),
                           situacao=row['situacao'], causa_paralisacao=row['causa_paralisacao'],
                           label_atual=row['label_risco'], snapshot_sha256=fingerprint(row),
                           encaminhamento=action, documentos=docs,
                           trechos_candidatos=best[row['id_fato']],
                           proxima_acao=('Conferir documentos e coletar, se necessario, laudo, relatorio de auditoria '
                                        'ou termo de paralisacao da mesma obra, ate a data-base; '
                                        'registrar causa com trecho/data/fonte e importar revisao.')))
    return dict(total=len(result), por_encaminhamento=dict(counts), obras=result,
                rotulos_atribuidos=0, aviso='Pacote de recuperacao; nenhum trecho constitui causa homologada.')


def recovery_report(conn):
    from src.database.labeling import read_rows
    rows = [r for r in read_rows(conn) if eligible(r)]
    ids = [r['id_fato'] for r in rows]
    with conn.cursor(row_factory=dict_row) as cur:
        docs = cur.execute('''SELECT DISTINCT p.id_fato,d.id_documento,d.origem_documento,
            d.tipo_documento,d.caminho_pdf_relativo,d.caminho_txt_relativo,d.sha256_pdf,d.sha256_txt,
            d.num_obras,d.ano_base,d.metadados
            FROM tcc.ponte_documento_embedding p JOIN tcc.dim_documento d USING(id_documento)
            WHERE p.id_fato=ANY(%s) AND d.ano_base=2025 ORDER BY p.id_fato,d.id_documento''', (ids,)).fetchall()
    with conn.cursor(name='sprint5_recuperacao', row_factory=dict_row) as cur:
        cur.itersize = 512
        cur.execute('''SELECT p.id_fato,p.id_documento,p.id_embedding,p.posicao_chunk,
            p.char_inicio,p.char_fim,e.conteudo_chunk
            FROM tcc.ponte_documento_embedding p JOIN tcc.dim_documento d USING(id_documento)
            JOIN tcc.dim_embedding e USING(id_embedding)
            WHERE p.id_fato=ANY(%s) AND d.ano_base=2025
                AND d.origem_documento IN ('original','nao_confirmada')
            ORDER BY p.id_fato,p.id_documento,p.posicao_chunk''', (ids,))
        return build_recovery(rows, docs, cur)
