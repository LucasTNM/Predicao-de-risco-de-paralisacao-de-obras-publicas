import pytest

from scripts.benchmark_embeddings_sprint4 import bucket_for, retain_sample, project_seconds, parse_df


def test_boundaries_and_no_truncation():
    assert bucket_for(128) == 128
    assert bucket_for(129) == 256
    assert bucket_for(4580) == 8192
    with pytest.raises(ValueError):
        bucket_for(8193)


def test_sample_is_bounded_and_independent_of_input_order():
    rows = [(i, str(i)*64, 'texto', 100) for i in range(1, 10)]
    forward, reverse = [], []
    for row in rows:
        retain_sample(forward, row, 3)
    for row in reversed(rows):
        retain_sample(reverse, row, 3)
    assert sorted(forward) == sorted(reverse)
    assert len(forward) == 3


def test_projection_weights_population_not_sample_size():
    assert project_seconds({128: 100, 512: 900}, {128: .1, 512: .5}) == 460
    with pytest.raises(ValueError):
        project_seconds({128: 100, 512: 900}, {128: .1})


def test_disk_report_bytes_and_fail_closed():
    assert parse_df('Filesystem 1B-blocks Used Available Use% Mounted on\n/dev/sdc 1000 200 750 22% /var/lib/postgresql/data\n')['available_bytes'] == 750
    with pytest.raises(ValueError):
        parse_df('permission denied')
