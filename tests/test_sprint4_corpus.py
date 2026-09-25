from copy import deepcopy
import json
from unittest.mock import Mock

import pytest

from src.database.embedding_corpus import prepare_corpus, validate_corpus
from scripts.auditar_embeddings_sprint4 import compare_vectors, compare_baseline
from src.database.schema import TABLES


def test_corpus_freezes_all_ids_and_rejects_tampering(tmp_path):
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [(i, str(i).zfill(64), 'config') for i in range(1, 515)]
    path = tmp_path/'corpus.json'
    manifest = prepare_corpus(conn, path, device='cpu', inference_batch=2, threads=8)
    assert manifest['config']['total'] == 514
    assert [p['count'] for p in manifest['config']['parts']] == [512, 2]
    validate_corpus(manifest, path)
    wrong = deepcopy(manifest)
    wrong['config']['device'] = 'cuda'
    with pytest.raises(ValueError):
        validate_corpus(wrong, path)
    part = path.parent/manifest['config']['parts'][0]['file']
    data = json.loads(part.read_text(encoding='utf-8'))
    data['selection'][0]['id_embedding'] = 987
    part.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        validate_corpus(manifest, path)
    with pytest.raises(FileExistsError):
        prepare_corpus(conn, path, device='cpu', inference_batch=2, threads=8)


def test_vector_comparison_distinguishes_numeric_rounding_from_wrong_vector():
    a = [1.0] + [0.0]*767
    assert compare_vectors(a, [1.0]+[1e-7]*767)['valido']
    assert not compare_vectors(a, [0.0,1.0]+[0.0]*766)['valido']


def test_final_audit_rejects_changed_content_even_with_same_counts():
    baseline = dict(valido=True, modelo='gte', revisao='a'*40, revisao_codigo='b'*40,
                    fingerprints={t:'hash' for t in TABLES}, integridade={'contagens': {t:2 for t in TABLES}})
    report = deepcopy(baseline)
    assert compare_baseline(report, baseline)['valido']
    report['fingerprints']['dim_documento'] = 'different'
    result = compare_baseline(report, baseline)
    assert not result['valido'] and result['contagens_preservadas']
    assert result['tabelas_alteradas'] == ['dim_documento']
    with pytest.raises(ValueError, match='baseline_incompleto'):
        compare_baseline(report, {})


def test_corpus_checkpoint_failure_preserves_parts_for_resume(tmp_path):
    from unittest.mock import patch
    from src.database.embedding_corpus import run_corpus
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [(i, str(i).zfill(64), 'config') for i in range(1, 515)]
    conn.execute.return_value.fetchone.return_value = (True,)
    path = tmp_path/'corpus.json'
    manifest = prepare_corpus(conn, path, device='cpu', inference_batch=2, threads=8)
    def batch(conn, child, child_path, **kwargs):
        if len(child['selection']) == 2:
            raise RuntimeError('falha na segunda parte')
        child['items'] = [dict(estado='gravado') for _ in child['selection']]
    with patch('src.database.embedding_corpus.run_batches', side_effect=batch):
        with pytest.raises(RuntimeError):
            run_corpus(conn, manifest, path, write=True)
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['status'] == 'INTERROMPIDO'
    assert saved['completed'] == 512
    assert len(saved['config']['parts']) == 2
    validate_corpus(saved, path)


def test_corpus_refuses_second_writer_before_inference(tmp_path):
    from unittest.mock import patch
    from src.database.embedding_corpus import run_corpus
    conn = Mock()
    conn.execute.return_value.fetchall.return_value = [(1, 'a'*64, 'config')]
    conn.execute.return_value.fetchone.return_value = (False,)
    path = tmp_path/'corpus.json'
    manifest = prepare_corpus(conn, path, device='cpu', inference_batch=2, threads=8)
    loader = Mock()
    with pytest.raises(ValueError, match='outra_carga_integral'):
        run_corpus(conn, manifest, path, write=True, loader=loader)
    loader.assert_not_called()
