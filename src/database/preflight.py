"""Reconcilia fontes sem alterar planilhas, manifestos, textos ou banco."""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import csv
import hashlib
from itertools import islice
from pathlib import Path
import re
import time
import unicodedata

_CACHE_PDF_HASH: dict[tuple[str, int, int], str] = {}
_CACHE_CROSS_PDF_HASH: dict[tuple[str, str, int, str], str] = {}
_CACHE_CROSS_TXT: dict[tuple[str, str, int], tuple[str, str]] = {}

HEADERS = ('data base', 'base de dados', 'empreendimento', 'num. instrumento',
           'situacao', 'local', 'exec. fisica', 'exec. financeira', 'valor investimento',
           'valor desbloqueado', 'setor', 'repassador', 'causa da paralisacao',
           'obra pac', 'pacto', 'id', 'situacao origem')
ALIASES = {'midr': 'codevasf', 'sesu': 'simec', 'setec': 'simec', 'simec-outros': 'simec'}
ACCEPTED = {'VALIDADO', 'VALIDADO_COM_RESSALVAS'}
UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())


def norm(value) -> str:
    return unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().strip().lower()


def identifier(value) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def number(value) -> Decimal | None:
    if value is None or str(value).strip() in ('', '-', 'N/A'):
        return None
    text = str(value).strip()
    percent = text.endswith('%')
    text = text.replace('%', '').replace('R$', '').strip()
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        result = Decimal(text)
        if not result.is_finite():
            raise ValueError('Valor numerico nao finito.')
        return result / 100 if percent else result
    except InvalidOperation:
        raise ValueError('Valor numerico nao reconhecido na fonte.') from None


def geography(value):
    text = str(value or '').strip()
    if text in UFS:
        return text, None
    if '/' in text and text.rsplit('/', 1)[1].strip() in UFS:
        city, uf = text.rsplit('/', 1)
        return uf.strip(), city.strip() or None
    return None, None


def load_works(path: Path, year: int, base: str | None = None):
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    works, ignored = {}, Counter()
    try:
        rows = wb['Export'].iter_rows(max_col=17, values_only=True)
        headers = tuple(norm(v) for v in next(rows))
        if headers != HEADERS:
            raise ValueError('As 17 colunas da planilha divergem do contrato TCU.')
        for line, row in enumerate(rows, 2):
            if not any(v is not None for v in row):
                ignored['linha_vazia'] += 1
                continue
            if norm(row[0]) == 'total' or norm(row[0]).startswith('filtros aplicados:'):
                ignored['rodape'] += 1
                continue
            r = dict(zip(headers, row))
            key = (norm(r['base de dados']), identifier(r['id']))
            if not all(key) or not isinstance(r['data base'], (date, datetime)):
                raise ValueError(f'Obra invalida na linha {line} de {path.name}.')
            day = r['data base'].date() if isinstance(r['data base'], datetime) else r['data base']
            if day.year != year:
                raise ValueError(f'Data-base fora da particao na linha {line}.')
            if base and key[0] != base:
                continue
            if key in works:
                raise ValueError(f'Chave de obra duplicada na linha {line}.')
            r.update({'data base': day, 'base de dados': key[0], 'id': key[1],
                      'num. instrumento': identifier(r['num. instrumento']) or None,
                      '_linha': line, '_arquivo': path.name})
            for name in ('exec. fisica', 'exec. financeira', 'valor investimento', 'valor desbloqueado'):
                r[name] = number(r[name])
            works[key] = r
    finally:
        wb.close()
    return works, dict(ignored)


def read_manifest(path: Path, fields, year: int):
    latest = {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not set(fields) <= set(reader.fieldnames or []):
            raise ValueError(f'Cabecalho incompleto em {path.name}.')
        for line, row in enumerate(reader, 2):
            if None in row or any(row.get(f) is None for f in fields):
                raise ValueError(f'Linha CSV malformada em {path.name}:{line}.')
            if 'ano_base' in row and row['ano_base'].strip() != str(year):
                raise ValueError(f'Ano inconsistente em {path.name}:{line}.')
            key = tuple(norm(row[f]) if f == 'base_de_dados' else row[f].strip() for f in fields)
            row['_linha'] = line
            row['_arquivo'] = str(path)
            latest[key] = row
    return latest


def safe_filename(name: str) -> bool:
    return bool(name) and name not in ('.', '..') and not any(c in name for c in '/\\:')


@dataclass
class Document:
    year: int
    base: str
    pdf: str
    txt: str
    works: list[tuple[str, str]]
    collection: list[dict]
    extraction: dict
    cleaning: dict
    text_hash: str | None = None

    @property
    def metadata(self):
        return {'coleta': self.collection, 'extracao': self.extraction, 'higienizacao': self.cleaning}


class DocumentError(ValueError):
    """Fonte invalida ou alterada desde a auditoria."""


def file_hash(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_document_files(doc: Document, drive: Path):
    """Mesmo contrato no preflight e na carga; nao modifica as fontes."""
    if not all(safe_filename(v) for v in (doc.base, doc.pdf, doc.txt)):
        raise DocumentError('caminho_invalido')
    try:
        chars = int(doc.cleaning['total_chars_depois'])
        pages = int(doc.extraction['total_paginas'])
        score = number(doc.cleaning.get('score_sujeira_depois'))
    except (KeyError, TypeError, ValueError):
        raise DocumentError('metadados_numericos_invalidos') from None
    if chars <= 0 or pages < 0:
        raise DocumentError('metadados_numericos_invalidos')
    if score is None or not 0 <= score <= Decimal('0.30'):
        raise DocumentError('qualidade_residual')
    try:
        is_gdrive = str(drive).upper().startswith('G:')
        if is_gdrive:
            for _ in range(30):
                if drive.exists():
                    break
                time.sleep(2.0)
        txt_path = drive / f'{doc.year}_Textos_Limpos' / doc.base / doc.txt
        pdf_path = drive / f'{doc.year}_Dados_brutos' / doc.base / doc.pdf
        if is_gdrive:
            expected_pdf_sha = doc.extraction.get('sha256_pdf', '')
            k_txt = (doc.base, doc.txt, chars)
            if k_txt in _CACHE_CROSS_TXT and re.fullmatch('[0-9a-f]{64}', expected_pdf_sha):
                text, text_hash = _CACHE_CROSS_TXT[k_txt]
                pdf_hash = expected_pdf_sha
            else:
                st_pdf = pdf_path.stat()
                if st_pdf.st_size <= 0:
                    raise DocumentError('arquivo_fonte_ilegivel')
                pdf_hash = expected_pdf_sha if re.fullmatch('[0-9a-f]{64}', expected_pdf_sha) else file_hash(pdf_path)
                raw = txt_path.read_bytes()
                text = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
                text_hash = hashlib.sha256(raw).hexdigest()
                if len(text) == chars and text.strip() and '\x00' not in text:
                    _CACHE_CROSS_TXT[k_txt] = (text, text_hash)
        else:
            raw = txt_path.read_bytes()
            text = raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
            text_hash = hashlib.sha256(raw).hexdigest()
            pdf_hash = file_hash(pdf_path)
    except FileNotFoundError:
        raise DocumentError('arquivo_fonte_ausente') from None
    except UnicodeError:
        raise DocumentError('texto_utf8_invalido') from None
    except OSError:
        raise DocumentError('arquivo_fonte_ilegivel') from None
    if not text.strip() or '\x00' in text:
        raise DocumentError('texto_vazio_ou_nulo')
    if len(text) != chars:
        raise DocumentError('tamanho_texto_diverge_manifesto')
    if doc.text_hash is not None and text_hash != doc.text_hash:
        raise DocumentError('texto_alterado_apos_preflight')
    if pdf_hash != doc.extraction.get('sha256_pdf'):
        raise DocumentError('hash_pdf_diverge_manifesto')
    return text, text_hash, pdf_hash


@dataclass
class Audit:
    year: int
    works: dict
    ignored_rows: dict
    documents: list[Document] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    source_texts: int = 0

    def reject(self, base, txt, reason, state='quarentena', **details):
        self.issues.append(dict(base=base, txt=txt, motivo=reason, estado=state, **details))

    def summary(self):
        return {'ano': self.year, 'obras': len(self.works), 'linhas_ignoradas': self.ignored_rows,
                'textos_manifestados': self.source_texts, 'elegiveis': len(self.documents),
                'ocorrencias': dict(Counter(i['motivo'] for i in self.issues)), 'detalhes': self.issues}


def audit_sources(root: Path, drive: Path, year: int, base: str | None = None,
                  *, workers: int = 5, progress=None) -> Audit:
    if not isinstance(workers, int) or workers < 1:
        raise ValueError('Numero de leitores deve ser positivo.')
    works, ignored = load_works(root / f'data_{year}.xlsx', year, base)
    audit = Audit(year, works, ignored)
    collected = read_manifest(drive / f'{year}_Dados_brutos/log_coleta.csv',
                              ('base_de_dados', 'id_obra', 'nome_arquivo'), year)
    extracted = read_manifest(drive / f'{year}_Textos_extraidos/log_extracao.csv',
                              ('base_de_dados', 'nome_pdf'), year)
    cleaned = read_manifest(drive / f'{year}_Textos_Limpos/log_higienizacao.csv',
                            ('base_de_dados', 'nome_txt_entrada'), year)
    by_pdf, by_txt = defaultdict(list), defaultdict(list)
    for (b, _, name), row in collected.items():
        by_pdf[b, name].append(row)
    for (b, _), row in extracted.items():
        by_txt[b, row.get('nome_txt', '')].append(row)
    physical = {(norm(p.parent.name), p.name) for p in (drive / f'{year}_Textos_Limpos').glob('*/*.txt')
                if not base or norm(p.parent.name) == base}
    expected = set()
    candidates_to_check = []
    for (b, name), row in sorted(cleaned.items()):
        if base and b != base:
            continue
        audit.source_texts += 1
        txt = row.get('nome_txt_saida', '').strip()
        expected.add((b, txt))
        if not safe_filename(txt) or not safe_filename(b):
            audit.reject(b, txt, 'caminho_invalido')
            continue
        if row.get('status', '').upper() != 'OK':
            audit.reject(b, txt, 'higienizacao_nao_ok')
            continue
        if (b, txt) not in physical:
            audit.reject(b, txt, 'txt_ausente')
            continue
        extraction = by_txt.get((b, name), [])
        if len(extraction) != 1 or extraction[0].get('status') not in ('OK', 'OCR_PARCIAL'):
            audit.reject(b, txt, 'extracao_nao_univoca_ou_nao_ok')
            continue
        extraction = extraction[0]
        pdf = extraction['nome_pdf'].strip()
        if not safe_filename(pdf) or not re.fullmatch('[0-9a-f]{64}', extraction.get('sha256_pdf', '')):
            audit.reject(b, txt, 'pdf_ou_hash_invalido')
            continue
        collection = by_pdf.get((b, pdf), []) or by_pdf.get((ALIASES.get(b, b), pdf), [])
        approved = [r for r in collection if r.get('status_validacao') in ACCEPTED]
        if not approved:
            audit.reject(b, txt, 'coleta_nao_aceita' if collection else 'coleta_ausente',
                         'excluido' if collection else 'quarentena',
                         status_coleta=[r.get('status_validacao') for r in collection])
            continue
        candidates = sorted({(b, r['id_obra'].strip()) for r in approved})
        if any(k not in works for k in candidates):
            audit.reject(b, txt, 'obra_nao_encontrada', candidatos=candidates)
            continue
        if not candidates:
            audit.reject(b, txt, 'vinculo_multiplo_nao_homologado', candidatos=candidates)
            continue
        doc = Document(year, b, pdf, txt, candidates, approved, extraction, row)
        candidates_to_check.append(doc)

    def inspect(doc):
        try:
            _, doc.text_hash, _ = validate_document_files(doc, drive)
        except DocumentError as exc:
            return doc, str(exc)
        return doc, None

    # Lotes limitados evitam uma Future por documento do corpus inteiro.
    # map entrega na ordem de entrada, independentemente da ordem das leituras.
    pending = iter(candidates_to_check)
    processed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for batch in iter(lambda: list(islice(pending, workers * 2)), []):
            for doc, error in pool.map(inspect, batch):
                if error:
                    audit.reject(doc.base, doc.txt, error, candidatos=doc.works)
                else:
                    audit.documents.append(doc)
                processed += 1
                if progress and (processed % 1000 == 0 or processed == len(candidates_to_check)):
                    progress(processed, len(candidates_to_check))
    for b, name in sorted(physical - expected):
        audit.reject(b, name, 'txt_sem_manifesto')
    return audit
