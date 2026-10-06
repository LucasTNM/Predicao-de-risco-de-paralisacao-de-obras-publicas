"""Politica conservadora derivada do PCC e ADR-001, sem inferencia por substring."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import unicodedata

VERSION = 'pcc-adr001-conservadora-v1'
SCHEMA = 'sprint5/v1'
CLASSES = {0: 'Regular / sem risco evidenciado', 1: 'Deficiência técnica',
           2: 'Deficiência orçamentário-financeira', 3: 'Abandono da contratada'}
# Cada entrada e uma correspondencia integral, nao um gatilho de palavras.
RULES = [
    ('T01', 1, 'Dificuldade técnica do Tomador', 'Incapacidade técnica institucional; PCC 2.4.2.'),
    ('T02', 1, 'Deficiência do Projeto', 'Falha de projeto; PCC 2.4.2.'),
    ('T03', 1, 'Licenciamento ambiental', 'Licença ambiental; ADR-001.'),
    ('T04', 1, 'Problemas técnicos da obra', 'Causa técnica explícita; PCC 2.4.2.'),
    ('F01', 2, 'Paralisação por falta de pagamento à empresa executora', 'Falta de pagamento; PCC 2.4.2/ADR-001.'),
    ('F02', 2, 'Atraso no Pagamento Construtora', 'Atraso no pagamento; PCC 2.4.2/ADR-001.'),
    ('F03', 2, 'Falta de aporte de contrapartida', 'Contrapartida; PCC 2.4.2.'),
    ('F04', 2, 'ORCAMENTARIA/FINANCEIRA UNIAO', 'Fluxo financeiro da União; PCC 2.4.2.'),
    ('F05', 2, 'Orçamentário/Financeiro', 'Causa orçamentário-financeira explícita; PCC 2.4.2.'),
    ('A01', 3, 'Abandono da empresa', 'Abandono explícito; PCC 2.4.2.'),
    ('A02', 3, 'Abandono pela empresa', 'Abandono explícito; PCC 2.4.2.'),
    ('A03', 3, 'ABANDONO POR PARTE DA CONTRATADA', 'Abandono explícito; PCC 2.4.2.'),
    ('A04', 3, 'PEDIDO DE DISTRATO AMIGAVÉL POR PARTE DA CONTRATADA (RECISÃO).',
     'Desistência expressa da contratada; ADR-001.'),
]
INPUT_FIELDS = ('id_fato', 'id_obra', 'ano_base', 'data_base', 'base_de_dados', 'id_tcu',
                'situacao', 'situacao_origem', 'fonte', 'causa_paralisacao',
                'exec_fisica', 'exec_financeira', 'valor_investimento', 'valor_desbloqueado')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def normalize(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text or '')
                           if not unicodedata.combining(c)).casefold().split())


def policy_hash():
    # Inclui semantica executavel, alem do catalogo, para detectar alteracoes sem bump.
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def fingerprint(row):
    return digest({key: row[key] for key in INPUT_FIELDS})


def in_scope(row):
    return row['ano_base'] == 2025 and date.fromisoformat(str(row['data_base'])).year == 2025


def classify(row):
    label, rule, reason = None, None, 'causa_nao_mapeada_ou_ambigua'
    cause = normalize(row['causa_paralisacao'])
    if not in_scope(row):
        reason = 'fora_corte_2025'
    elif cause in ('', '-', 'nao informado'):
        reason = 'sem_evidencia_causal_regularidade_requer_revisao'
    elif normalize(row['situacao']) != 'paralisada':
        reason = 'conflito_situacao_causa'
    else:
        for code, target, literal, _ in RULES:
            if cause == normalize(literal):
                label, rule, reason = target, code, 'causa_exata_catalogada'
                break
        if label is None and (',' in cause or ';' in cause):
            reason = 'multicausal_ou_texto_livre'
    return dict(label_risco=label, regra=rule, motivo=reason)


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_review(row, review):
    """Verifica declaracao do revisor; nao autentica identidade nem veracidade da fonte."""
    if not isinstance(review, dict) or not in_scope(row):
        raise ValueError('revisao_fora_corte_2025_ou_invalida')
    label = review.get('label_risco')
    if type(label) is not int or label not in CLASSES:
        raise ValueError('classe_invalida')
    if type(review.get('id_fato')) is not int or review['id_fato'] != row['id_fato']:
        raise ValueError('identidade_divergente')
    if review.get('snapshot_sha256') != fingerprint(row):
        raise ValueError('snapshot_alterado')
    if not all(_nonempty(review.get(k)) for k in ('revisor', 'justificativa')):
        raise ValueError('revisor_ou_justificativa_ausente')
    if label == 0 and review.get('regularidade_sem_apontamentos_graves') is not True:
        raise ValueError('classe_zero_exige_evidencia_positiva_de_regularidade')
    evidence = review.get('evidencia')
    if not isinstance(evidence, dict) or evidence.get('origem') != 'original':
        raise ValueError('evidencia_nao_original')
    if not all(_nonempty(evidence.get(k)) for k in ('caminho', 'sha256', 'data', 'trecho')):
        raise ValueError('evidencia_incompleta')
    try:
        when = date.fromisoformat(evidence['data'])
    except (ValueError, TypeError):
        raise ValueError('data_evidencia_invalida') from None
    if when > date.fromisoformat(str(row['data_base'])):
        raise ValueError('evidencia_posterior_data_base')
    try:
        raw = Path(evidence['caminho']).read_bytes()
        text = raw.decode('utf-8-sig')
    except (OSError, UnicodeError):
        raise ValueError('evidencia_ausente_ou_nao_utf8') from None
    if hashlib.sha256(raw).hexdigest() != evidence['sha256']:
        raise ValueError('hash_evidencia_divergente')
    if evidence['trecho'] not in text:
        raise ValueError('trecho_nao_encontrado')
    return dict(label_risco=label, regra=None, motivo='decisao_revisada', revisao=review)


def provenance_errors(row):
    """Auditoria recomputa regras e snapshots; nao aceita simples origem nao vazia."""
    if row['label_risco'] is None:
        return [] if row['status_rotulagem'] == 'PENDENTE' and row['origem_rotulo'] is None else ['pendente_inconsistente']
    try:
        p = json.loads(row['origem_rotulo'])
        if not isinstance(p, dict):
            return ['proveniencia_invalida']
        if (not in_scope(row) or p.get('schema') != SCHEMA or p.get('versao') != VERSION
                or p.get('politica_sha256') != policy_hash()
                or p.get('snapshot_sha256') != fingerprint(row)
                or type(p.get('id_fato')) is not int
                or p.get('id_fato') != row['id_fato']
                or type(p.get('label_risco')) is not int
                or p['label_risco'] != row['label_risco']
                or row['status_rotulagem'] != 'ROTULADO'
                or not _nonempty(p.get('executado_em')) or not _nonempty(p.get('executor'))):
            return ['proveniencia_divergente']
        if datetime.fromisoformat(p['executado_em']).tzinfo is None:
            return ['data_execucao_sem_timezone']
        if p.get('metodo') == 'regra':
            expected = classify(row)
            if expected['label_risco'] != row['label_risco'] or expected['regra'] != p.get('regra'):
                return ['regra_divergente']
        elif p.get('metodo') == 'revisao':
            if validate_review(row, p.get('revisao'))['label_risco'] != row['label_risco']:
                return ['revisao_divergente']
        else:
            return ['metodo_desconhecido']
    except (ValueError, TypeError, KeyError):
        return ['proveniencia_ou_evidencia_invalida']
    return []
