from pathlib import Path
import hashlib

from scripts.auditar_proveniencia_sprint3 import inspect_document


def test_physical_hash_change_rejects_previously_intact_chain(tmp_path):
    row = dict(id_documento=1, ano_base=2025, origem_documento='nao_confirmada',
        caminho_pdf_relativo='dnit/a.pdf', caminho_txt_relativo='dnit/a.txt',
        sha256_pdf=hashlib.sha256(b'pdf').hexdigest(), sha256_txt=hashlib.sha256(b'texto').hexdigest(),
        metadados={'coleta': [{'status_validacao': 'VALIDADO'}],
                   'extracao': {'status': 'OK'}, 'higienizacao': {'status': 'OK'}})
    for directory, filename, content in [('2025_Dados_brutos', 'a.pdf', b'pdf'),
                                          ('2025_Textos_Limpos', 'a.txt', b'texto')]:
        path = tmp_path / directory / 'dnit' / filename
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
    assert inspect_document(row, tmp_path)['cadeia_integra']
    (tmp_path / '2025_Textos_Limpos/dnit/a.txt').write_bytes(b'alterado')
    result = inspect_document(row, tmp_path)
    assert not result['cadeia_integra']
    assert 'txt_hash_divergente' in result['falhas']


def test_missing_file_and_url_do_not_confirm_origin(tmp_path):
    row = dict(id_documento=1, ano_base=2025, origem_documento='nao_confirmada',
               caminho_pdf_relativo='dnit/missing.pdf', caminho_txt_relativo='dnit/missing.txt',
               sha256_pdf='a'*64, sha256_txt='b'*64,
               metadados={'coleta':[{'status_validacao':'VALIDADO','url_origem':'https://www.gov.br/a.pdf'}],
                          'extracao':{'status':'OK'},'higienizacao':{'status':'OK'}})
    result=inspect_document(row, tmp_path)
    assert not result['cadeia_integra']
    assert result['origem_registrada']=='nao_confirmada'
    assert result['homologacao_original'] is False


def test_path_escape_is_rejected(tmp_path):
    row=dict(id_documento=1,ano_base=2025,origem_documento='nao_confirmada',
             caminho_pdf_relativo='../outside.pdf',caminho_txt_relativo='x/a.txt',
             sha256_pdf='a'*64,sha256_txt='b'*64,metadados={})
    assert 'caminho_invalido' in inspect_document(row,tmp_path)['falhas']
