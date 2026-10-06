import pytest
from src.extractors.pncp_identity import parse_control, verified_record

CNPJ = '04308975000118'

class Response:
    status_code = 200
    def __init__(self, data): self.data = data
    def json(self): return self.data

class Session:
    def __init__(self, data): self.data, self.calls = data, []
    def get(self, url, **kwargs):
        self.calls.append(url)
        return Response(self.data)

def test_local_number_never_queries_pncp():
    session = Session({})
    assert verified_record(session, CNPJ, {'num. instrumento': '06 00766/2024'}) is None
    assert session.calls == []

def test_contract_only_and_verified_fields():
    control = CNPJ + '-2-000123/2024'
    row = {'pncp_controle': control, 'num. instrumento': '06 00766/2024', 'empreendimento': 'Obra BR-040 MG'}
    data = {'numeroControlePNCP': control, 'orgaoEntidade': {'cnpj': CNPJ},
            'numeroContratoEmpenho': '06 00766/2024', 'objetoContrato': 'Obra BR-040 MG'}
    session = Session(data)
    result = verified_record(session, CNPJ, row)
    assert result['url'].endswith('/contratos/2024/123')
    assert len(session.calls) == 1
    assert '/compras/' not in session.calls[0]
    data['objetoContrato'] = 'Aquisição de material de escritório'
    assert verified_record(session, CNPJ, row) is None

def test_wrong_org_and_purchase_cannot_borrow_contract_number():
    session = Session({})
    assert verified_record(session, CNPJ, {'pncp_controle': '00000000000000-2-000123/2024'}) is None
    assert not session.calls
    assert verified_record(session, CNPJ, {'pncp_controle': CNPJ+'-1-000123/2024', 'num. instrumento': '123/2024'}) is None
    assert not session.calls

@pytest.mark.parametrize('value', [None, '766/2024', '123', 'http://evil', '04308975000118-3-123/2024'])
def test_invalid_controls(value):
    assert parse_control(value) is None


def test_collector_blocks_legacy_call_before_file_lookup(tmp_path):
    from src.extractors.pncp import coletar_obra_pncp
    session=Session({})
    result=coletar_obra_pncp(session,CNPJ,'DNIT','2024','766',
                           {'id':'1','num. instrumento':'06 00766/2024'},tmp_path,set())
    assert result==[]
    assert session.calls==[]
