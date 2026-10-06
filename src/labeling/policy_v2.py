"""Situacao primeiro, conforme autorizacao do pesquisador em 2026-09-28.

V1 permanece imutavel para auditar as proveniencias ja gravadas.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from src.labeling import policy as v1
from src.labeling.policy import (SCHEMA, canonical, fingerprint, in_scope, normalize,
                                 validate_review)

VERSION = 'pcc-situacao-causa-v2'
CLASSES = {**v1.CLASSES, 0: 'Regular pela situação (referência tabular)'}
RULES = [*v1.RULES, ('R00', 0, 'Em execução/Concluída sem causa e sem contradição',
                     'Regra autorizada pelo pesquisador em 2026-09-28.')]


def policy_hash():
    return hashlib.sha256(Path(__file__).read_bytes() + v1.policy_hash().encode('ascii')).hexdigest()


def missing_cause(value):
    return normalize(value) in ('', '-', 'nao informado')


def classify(row):
    pending = dict(label_risco=None, regra=None)
    if not in_scope(row):
        return {**pending, 'motivo': 'fora_corte_2025'}
    status = normalize(row['situacao'])
    if status in ('em execucao', 'concluida'):
        if not missing_cause(row['causa_paralisacao']):
            return {**pending, 'motivo': 'conflito_situacao_causa'}
        origin = normalize(row['situacao_origem'])
        if re.search(r'paralis|cancel|inacabad|rescind|rescis|reinici|nao executad|'
                     r'com pendenc|sem etapa util|nao iniciad', origin):
            return {**pending, 'motivo': 'situacao_origem_contraditoria_revisar'}
        return dict(label_risco=0, regra='R00', motivo='regular_pela_situacao_sem_contradicao')
    if status == 'paralisada':
        if missing_cause(row['causa_paralisacao']):
            return {**pending, 'motivo': 'paralisada_sem_causa_recuperar_evidencia'}
        return v1.classify(row)
    return {**pending, 'motivo': 'situacao_nao_mapeada'}


def provenance_errors(row):
    if row['label_risco'] is None:
        return v1.provenance_errors(row)
    try:
        p = json.loads(row['origem_rotulo'])
        if not isinstance(p, dict):
            return ['proveniencia_invalida']
        if p.get('versao') == v1.VERSION:
            return v1.provenance_errors(row)
        if (not in_scope(row) or p.get('schema') != SCHEMA or p.get('versao') != VERSION
                or p.get('politica_sha256') != policy_hash()
                or p.get('snapshot_sha256') != fingerprint(row)
                or type(p.get('id_fato')) is not int or p['id_fato'] != row['id_fato']
                or type(p.get('label_risco')) is not int or p['label_risco'] != row['label_risco']
                or row['status_rotulagem'] != 'ROTULADO'
                or not v1._nonempty(p.get('executado_em')) or not v1._nonempty(p.get('executor'))):
            return ['proveniencia_divergente']
        if datetime.fromisoformat(p['executado_em']).tzinfo is None:
            return ['data_execucao_sem_timezone']
        if p.get('metodo') in ('regra', 'regra_situacao'):
            expected = classify(row)
            method = 'regra_situacao' if expected['regra'] == 'R00' else 'regra'
            if (expected['label_risco'] != row['label_risco'] or expected['regra'] != p.get('regra')
                    or method != p['metodo']):
                return ['regra_divergente']
        elif p.get('metodo') == 'revisao':
            if validate_review(row, p.get('revisao'))['label_risco'] != row['label_risco']:
                return ['revisao_divergente']
        else:
            return ['metodo_desconhecido']
    except (ValueError, TypeError, KeyError):
        return ['proveniencia_ou_evidencia_invalida']
    return []
