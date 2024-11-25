import pytest
from make_argocd_fly.params import populate_params, get_params


def test_populate_params():
    populate_params(
        root_dir='custom_root_dir',
        config_file='custom_config_file.yml',
        source_dir='custom_source_dir',
        output_dir='custom_output_dir',
        tmp_dir='custom_tmp_dir',
        var_identifier='custom_var_identifier',
        loglevel='custom_loglevel',

    )
    params = get_params()
    assert params.get_root_dir() == 'custom_root_dir'
    assert params.get_config_file() == 'custom_config_file.yml'
    assert params.get_source_dir() == 'custom_source_dir'
    assert params.get_output_dir() == 'custom_output_dir'
    assert params.get_tmp_dir() == 'custom_tmp_dir'
    assert params.get_var_identifier() == 'custom_var_identifier'
    assert params.get_loglevel() == 'custom_loglevel'
