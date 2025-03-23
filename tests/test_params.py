import pytest
from make_argocd_fly.params import populate_params


def test_populate_params():
    params = populate_params(
        root_dir='custom_root_dir',
        config_file='custom_config_file.yml',
        source_dir='custom_source_dir',
        output_dir='custom_output_dir',
        tmp_dir='custom_tmp_dir',
        var_identifier='custom_var_identifier',
        loglevel='custom_loglevel',

    )

    assert params.root_dir == 'custom_root_dir'
    assert params.config_file == 'custom_config_file.yml'
    assert params.source_dir == 'custom_source_dir'
    assert params.output_dir == 'custom_output_dir'
    assert params.tmp_dir == 'custom_tmp_dir'
    assert params.var_identifier == 'custom_var_identifier'
    assert params.loglevel == 'custom_loglevel'
