from unittest.mock import Mock

import pytest

from src.embedding_model import encode_checked, MAX_TOKENS
from src.database.embeddings import validate_vector, EmbeddingError
from src.database.vector_search import retrieval_metrics, search_embeddings
from scripts.avaliar_busca_sprint4 import score_review


@pytest.mark.parametrize('vector', [[0.0]*768, [float('inf')]*768, [1.0]*767, [1.0]*768])
def test_invalid_vectors(vector):
    with pytest.raises(EmbeddingError):
        validate_vector(vector)


def test_token_limit_including_special_tokens():
    model = Mock(max_seq_length=MAX_TOKENS)
    model.tokenizer.return_value = {'length': [MAX_TOKENS]}
    model.encode.return_value = [[1.0]+[0.0]*767]
    assert encode_checked(model, ['texto'])[1] == [MAX_TOKENS]
    assert model.tokenizer.call_args.kwargs['truncation'] is False
    model.reset_mock()
    model.tokenizer.return_value = {'length': [MAX_TOKENS+1]}
    with pytest.raises(ValueError, match='truncar'):
        encode_checked(model, ['texto'])
    model.encode.assert_not_called()


def test_search_rejects_invalid_k_before_sql():
    conn = Mock()
    with pytest.raises(ValueError):
        search_embeddings(conn, [], model='m', revision='a'*40, k=0)
    conn.execute.assert_not_called()


def test_metrics_known_ranking_and_no_judgments():
    assert retrieval_metrics([9, 2, 3], [2, 3, 4], 3) == {
        'precision_at_k': 2/3, 'recall_at_k': 2/3, 'reciprocal_rank_at_k': 0.5}
    assert retrieval_metrics([9], [2], 3)['precision_at_k'] == 0
    with pytest.raises(ValueError):
        retrieval_metrics([9], [], 3)
    with pytest.raises(ValueError):
        retrieval_metrics([2, 2], [2], 3)


def test_review_requires_same_corpus_and_explicit_human_judgment():
    context = dict(corpus_hash='hash', universe=[1, 2], queries=['consulta'], rankings=[[2, 1]], k=2)
    review = dict(corpus_sha256='hash', tipo_revisao='humana', consultas=[dict(consulta='consulta',
        revisado_por='Revisor de teste', universo_revisado_integralmente=True, relevantes=[1])])
    assert score_review(review, **context)[0]['recall_at_k'] == 1
    with pytest.raises(ValueError, match='mudou'):
        score_review(review, **{**context, 'corpus_hash': 'outro'})
    review['consultas'][0]['revisado_por'] = None
    with pytest.raises(ValueError, match='pendente'):
        score_review(review, **context)


def test_assisted_review_requires_explicit_authorship():
    context = dict(corpus_hash='h', universe=[1], queries=['q'], rankings=[[1]], k=1)
    review = dict(corpus_sha256='h', consultas=[dict(consulta='q',
        revisado_por='Codex (IA)', universo_revisado_integralmente=True, relevantes=[])])
    with pytest.raises(ValueError, match='tipo'):
        score_review(review, **context)
    review['tipo_revisao'] = 'assistida_ia'
    assert score_review(review, **context)[0]['recall_at_k'] is None


def test_empty_text_never_reaches_inference():
    model = Mock()
    with pytest.raises(ValueError, match='texto vazio'):
        encode_checked(model, [' '])
    model.encode.assert_not_called()
