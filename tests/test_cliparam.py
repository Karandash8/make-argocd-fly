import pytest
from make_argocd_fly import default
from make_argocd_fly.cliparam import CLIParams, is_experimental_enabled, populate_cli_params
from make_argocd_fly.experimental import ExperimentalFeature, parse_experimental


def test_cli_params_default_cache_dir():
  cli_params = CLIParams()

  assert cli_params.cache_dir == default.CACHE_DIR


def test_populate_cli_params():
  cli_params = populate_cli_params(
    root_dir='custom_root_dir',
    source_dir='custom_source_dir',
    output_dir='custom_output_dir',
    cache_dir='custom_cache',
    tmp_dir='custom_tmp_dir',
    var_identifier='$',
    loglevel='custom_loglevel',

  )

  assert cli_params.root_dir == 'custom_root_dir'
  assert cli_params.source_dir == 'custom_source_dir'
  assert cli_params.output_dir == 'custom_output_dir'
  assert cli_params.cache_dir == 'custom_cache'
  assert cli_params.tmp_dir == 'custom_tmp_dir'
  assert cli_params.var_identifier == '$'
  assert cli_params.loglevel == 'custom_loglevel'


@pytest.mark.parametrize(
  ('value', 'expected_features', 'expected_unknown'),
  [
    (None, set(), []),
    ('', set(), []),
    (',,,', set(), []),
    ('incremental-output', {ExperimentalFeature.INCREMENTAL_OUTPUT}, []),
    ('incremental-output,unknown', {ExperimentalFeature.INCREMENTAL_OUTPUT}, ['unknown']),
    (' incremental-output , unknown ', {ExperimentalFeature.INCREMENTAL_OUTPUT}, ['unknown']),
    ('incremental-output,incremental-output', {ExperimentalFeature.INCREMENTAL_OUTPUT}, []),
    ('unknown', set(), ['unknown']),
  ],
)
def test_parse_experimental(value, expected_features, expected_unknown):
  features, unknown = parse_experimental(value)

  assert features == expected_features
  assert unknown == expected_unknown


def test_populate_cli_params_experimental_known_feature():
  cli_params = populate_cli_params(experimental='incremental-output')

  assert cli_params.experimental == {ExperimentalFeature.INCREMENTAL_OUTPUT}
  assert cli_params.unknown_experimental == []
  assert is_experimental_enabled(ExperimentalFeature.INCREMENTAL_OUTPUT)


def test_populate_cli_params_experimental_unknown_feature():
  cli_params = populate_cli_params(experimental='unknown')

  assert cli_params.experimental == set()
  assert cli_params.unknown_experimental == ['unknown']
  assert not is_experimental_enabled(ExperimentalFeature.INCREMENTAL_OUTPUT)


def test_populate_cli_params_experimental_none():
  cli_params = populate_cli_params(experimental=None)

  assert cli_params.experimental == set()
  assert cli_params.unknown_experimental == []
  assert not is_experimental_enabled(ExperimentalFeature.INCREMENTAL_OUTPUT)
