"""Fail-closed PNCP identity: local instrument numbers are not PNCP sequences."""
import re

import requests

from src.labeling.policy import normalize


def parse_control(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r'(\d{14})-([12])-(\d{1,6})/(\d{4})', value.strip())
    if not match or int(match[3]) == 0:
        return None
    cnpj, kind, sequence, year = match.groups()
    return dict(cnpj=cnpj, kind='compras' if kind == '1' else 'contratos',
                sequence=str(int(sequence)), year=year)


def instrument_key(value):
    # Preserve all numeric components (including regional office and year).
    if not isinstance(value, str):
        return ''
    return re.sub(r'[^a-z0-9]', '', normalize(value))


def verified_record(session, cnpj, row):
    """Resolve an explicit control number and verify the returned entity.

    Exact object comparison is intentionally conservative. Unresolved cases need
    reviewed crosswalks, never guessed IDs. This is identity, not causal evidence.
    """
    value = row.get('pncp_controle')
    if not isinstance(value, str):
        value = row.get('numeroControlePNCP')
    identity = parse_control(value)
    if not identity or identity['cnpj'] != cnpj:
        return None
    is_contract = identity['kind'] == 'contratos'
    local_number = row.get('num. instrumento') if is_contract else row.get('pncp_numero_compra')
    local_object = row.get('empreendimento')
    if not instrument_key(local_number) or not isinstance(local_object, str) or not local_object.strip():
        return None
    url = (f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/"
           f"{identity['kind']}/{identity['year']}/{identity['sequence']}")
    try:
        response = session.get(url, headers={'Accept': 'application/json'}, timeout=15)
        if response.status_code != 200:
            return None
        data = response.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if parse_control(data.get('numeroControlePNCP')) != identity:
        return None
    org = data.get('orgaoEntidade') or {}
    if not isinstance(org, dict) or org.get('cnpj') != cnpj:
        return None
    number = data.get('numeroContratoEmpenho' if is_contract else 'numeroCompra')
    obj = data.get('objetoContrato' if is_contract else 'objetoCompra')
    if instrument_key(number) != instrument_key(local_number):
        return None
    if not isinstance(obj, str) or normalize(obj) != normalize(local_object):
        return None
    return dict(**identity, url=url, control=value, metadata=data)
