import pytest
from make_argocd_fly.cliparam import populate_cli_params


def test_populate_cli_params():
    cli_params = populate_cli_params(
        root_dir='custom_root_dir',
        source_dir='custom_source_dir',
        output_dir='custom_output_dir',
        tmp_dir='custom_tmp_dir',
        var_identifier='$',
        loglevel='custom_loglevel',

    )

    assert cli_params.root_dir == 'custom_root_dir'
    assert cli_params.source_dir == 'custom_source_dir'
    assert cli_params.output_dir == 'custom_output_dir'
    assert cli_params.tmp_dir == 'custom_tmp_dir'
    assert cli_params.var_identifier == '$'
    assert cli_params.loglevel == 'custom_loglevel'
