from unittest.mock import Mock, patch
import pytest

from scripts.buscar_embeddings_sprint4 import query_text, main
from src.embedding_model import MAX_TOKENS, MODEL, REVISION


def test_text_query_uses_same_model_and_passes_filters():
    model = Mock(max_seq_length=MAX_TOKENS)
    model.tokenizer.return_value = {'length': [3]}
    model.encode.return_value = [[1.0]+[0.0]*767]
    with patch('scripts.buscar_embeddings_sprint4.search_embeddings', return_value=[]) as search:
        result = query_text(Mock(), model, 'obra', year=2025, origin='ficha_sintetica', k=7)
    assert search.call_args.kwargs == dict(model=MODEL, revision=REVISION, k=7, year=2025, origin='ficha_sintetica')
    assert result['tokens'] == 3 and result['resultados'] == []


@pytest.mark.parametrize('argv', [['--consulta',' '], ['--consulta','obra','--k','0']])
def test_search_cli_rejects_invalid_input_before_model(argv):
    with patch('sys.argv', ['buscar', *argv]), patch('scripts.buscar_embeddings_sprint4.load_model') as loader:
        with pytest.raises(SystemExit) as error:
            main()
    assert error.value.code == 2
    loader.assert_not_called()
