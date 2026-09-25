from copy import deepcopy
from unittest.mock import Mock

import pytest

from src.database.embedding_run import make_manifest, validate_manifest, run_batches


def test_cli_accepts_registered_synthetic_origin():
    from unittest.mock import patch, MagicMock
    from scripts.gerar_embeddings_sprint4 import main
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    with patch('sys.argv', ['gerar', '--limite', '2', '--origem', 'ficha_sintetica']), \
            patch('scripts.gerar_embeddings_sprint4.connect') as connection:
        connection.return_value.__enter__.return_value = conn
        main()
    assert conn.execute.call_args.args[1][2:4] == ('ficha_sintetica', 'ficha_sintetica')


@pytest.mark.parametrize('size', ['0', '-1', '33'])
def test_cli_rejects_invalid_batch_before_connection(size):
    from unittest.mock import patch
    from scripts.gerar_embeddings_sprint4 import main
    with patch('sys.argv', ['gerar', '--limite', '2', '--batch-size', size]), \
            patch('scripts.gerar_embeddings_sprint4.connect') as connection:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
        connection.assert_not_called()


def test_manifest_rejects_edit_and_duplicates():
    m = make_manifest([{'id_embedding': 1, 'chave_conteudo': 'a'*64, 'chunk_config': 'v1'}], year=2025, origin='nao_confirmada', batch_size=2)
    validate_manifest(m)
    changed = deepcopy(m)
    changed['selection'][0]['id_embedding'] = 2
    with pytest.raises(ValueError):
        validate_manifest(changed)
    with pytest.raises(ValueError):
        make_manifest(m['selection']*2, year=2025, origin=None, batch_size=2)


def test_all_completed_skip_model_and_encoder(tmp_path):
    # Banco simulado somente para probar a fronteira de inferencia; integracao real em outro teste.
    m = make_manifest([{'id_embedding': 1, 'chave_conteudo': 'a'*64, 'chunk_config': 'v1'}], year=2025, origin=None, batch_size=2)
    loader, encoder = Mock(), Mock()
    conn = Mock()
    conn.execute.return_value.fetchone.return_value = (True,)
    from unittest.mock import patch
    with patch('src.database.embedding_run.read_items', return_value=[dict(m['selection'][0], text='texto', done=True)]):
        run_batches(conn, m, tmp_path/'run.json', write=True, loader=loader, encoder=encoder)
    loader.assert_not_called()
    encoder.assert_not_called()
    assert m['status'] == 'CONCLUIDO'
    assert m['items'][0]['estado'] == 'reutilizado'
