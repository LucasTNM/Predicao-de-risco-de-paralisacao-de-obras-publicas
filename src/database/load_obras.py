"""Carga transacional das observacoes anuais sem multiplicar medidas por documento."""
from __future__ import annotations

import json

from psycopg import sql
from psycopg.types.json import Jsonb

from src.database.preflight import geography


def jsonb(value):
    return Jsonb(value, dumps=lambda x: json.dumps(x, ensure_ascii=False, default=str))


def load_works(conn, audit) -> dict:
    columns = ('base_de_dados', 'id_tcu', 'data_base', 'ano_base', 'num_instrumento',
               'empreendimento', 'situacao', 'situacao_origem', 'local_original', 'uf',
               'municipio', 'setor', 'repassador', 'obra_pac', 'pacto', 'fonte')
    names = sql.SQL(',').join(map(sql.Identifier, columns))
    with conn.transaction():
        # Mesmo ordenamento da rotulagem: evita intercalar fonte nova e alvo antigo.
        conn.execute('LOCK TABLE tcc.dim_obra,tcc.fato_risco IN SHARE ROW EXCLUSIVE MODE')
        conn.execute('CREATE TEMP TABLE incoming_works ON COMMIT DROP AS SELECT * FROM tcc.dim_obra WITH NO DATA')
        with conn.cursor().copy(sql.SQL('COPY incoming_works ({}) FROM STDIN').format(names)) as copy:
            for r in audit.works.values():
                uf, city = geography(r['local'])
                copy.write_row((r['base de dados'], r['id'], r['data base'], audit.year,
                                r['num. instrumento'], r['empreendimento'], r['situacao'],
                                r['situacao origem'], r['local'], uf, city, r['setor'],
                                r['repassador'], r['obra pac'], r['pacto'], jsonb(r)))
        # Situacao/fonte tambem integram a decisao, mesmo sem mudanca nas medidas.
        conn.execute('''
            UPDATE tcc.fato_risco f SET label_risco=NULL,origem_rotulo=NULL,
                status_rotulagem='PENDENTE',updated_at=now()
            FROM tcc.dim_obra o JOIN incoming_works i
                USING (base_de_dados,id_tcu,data_base)
            WHERE f.id_obra=o.id_obra AND o.fonte IS DISTINCT FROM i.fonte
                AND (f.label_risco IS NOT NULL OR f.origem_rotulo IS NOT NULL)
        ''')
        updates = sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c), sql.Identifier(c)) for c in columns[4:])
        conn.execute(sql.SQL('''
            INSERT INTO tcc.dim_obra ({names}) SELECT {names} FROM incoming_works
            ON CONFLICT (base_de_dados,id_tcu,data_base) DO UPDATE SET {updates}, updated_at=now()
            WHERE dim_obra.fonte IS DISTINCT FROM EXCLUDED.fonte
        ''').format(names=names, updates=updates))
        conn.execute('''
            INSERT INTO tcc.fato_risco (id_obra,ano_base,causa_paralisacao,exec_fisica,
                                       exec_financeira,valor_investimento,valor_desbloqueado)
            SELECT o.id_obra,o.ano_base,i.fonte->>'causa da paralisacao',
                   (i.fonte->>'exec. fisica')::numeric, (i.fonte->>'exec. financeira')::numeric,
                   (i.fonte->>'valor investimento')::numeric, (i.fonte->>'valor desbloqueado')::numeric
            FROM incoming_works i JOIN tcc.dim_obra o USING (base_de_dados,id_tcu,data_base)
            ON CONFLICT (id_obra) DO UPDATE SET
                causa_paralisacao=EXCLUDED.causa_paralisacao,exec_fisica=EXCLUDED.exec_fisica,
                exec_financeira=EXCLUDED.exec_financeira,valor_investimento=EXCLUDED.valor_investimento,
                valor_desbloqueado=EXCLUDED.valor_desbloqueado, label_risco=NULL,
                origem_rotulo=NULL,status_rotulagem='PENDENTE',updated_at=now()
            WHERE (fato_risco.causa_paralisacao,fato_risco.exec_fisica,fato_risco.exec_financeira,
                   fato_risco.valor_investimento,fato_risco.valor_desbloqueado) IS DISTINCT FROM
                  (EXCLUDED.causa_paralisacao,EXCLUDED.exec_fisica,EXCLUDED.exec_financeira,
                   EXCLUDED.valor_investimento,EXCLUDED.valor_desbloqueado)
        ''')
        rows = conn.execute('''
            SELECT o.base_de_dados,o.id_tcu,f.id_fato
            FROM incoming_works i JOIN tcc.dim_obra o USING (base_de_dados,id_tcu,data_base)
            JOIN tcc.fato_risco f ON f.id_obra = o.id_obra
        ''').fetchall()
        conn.execute('DROP TABLE pg_temp.incoming_works')
    return {(base, identifier): fact for base, identifier, fact in rows}
