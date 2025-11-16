import pytest

from make_argocd_fly.exception import OutputFilenameConstructionError
from make_argocd_fly.namegen import _normalize, K8sInfo, SourceInfo, Pattern, SourcePolicy, K8sPolicy, Deduper


##################
### _normalize
##################

def test_normalize__none():
  assert _normalize(None) is None

def test_normalize__empty_string():
  assert _normalize('') == ''

def test_normalize__whitespace_collapses_to_empty():
  # Whitespace is a truthy string; regex turns spaces into '-', strip removes them.
  assert _normalize('   ') == ''


def test_normalize__keeps_allowed_chars_and_lowercases():
  # Allowed: letters, digits, dot, underscore, hyphen. Also forces lowercase.
  assert _normalize('AbC.DEF-123_ghi') == 'abc.def-123_ghi'


def test_normalize__replaces_invalid_with_dash_and_strips_edges():
  # '@' becomes '-', multiple invalid collapse to single '-', leading/trailing '-' stripped
  assert _normalize('--My Chart@1.2.3--') == 'my-chart-1.2.3'


def test_normalize__unicode_and_punctuation_become_dashes():
  # Non-ASCII letters and em-dash become '-', then collapse and lowercase
  assert _normalize('naïve—Name') == 'na-ve-name'


def test_normalize__only_invalid_chars_results_in_empty():
  # All invalid replaced by '-' and then stripped, hence empty
  assert _normalize('%%%') == ''


def test_normalize__dots_and_underscores_preserved():
  assert _normalize('file.NAME_v1.2') == 'file.name_v1.2'


##################
# K8sInfo.from_yaml_obj
##################

def test_from_yaml_obj_full_fields():
  obj = {
    'apiVersion': 'apps/v1',
    'kind': 'Deployment',
    'metadata': {'name': 'grafana', 'namespace': 'monitoring'},
  }
  k = K8sInfo.from_yaml_obj(obj)
  assert k.api_version == 'apps/v1'
  assert k.group == 'apps'
  assert k.version == 'v1'
  assert k.kind == 'Deployment'
  assert k.name == 'grafana'
  assert k.namespace == 'monitoring'


def test_from_yaml_obj_core_v1_no_group():
  obj = {
    'apiVersion': 'v1',
    'kind': 'ConfigMap',
    'metadata': {'name': 'cm1'},
  }
  k = K8sInfo.from_yaml_obj(obj)
  assert k.api_version == 'v1'
  assert k.group is None
  assert k.version == 'v1'
  assert k.kind == 'ConfigMap'
  assert k.name == 'cm1'
  assert k.namespace is None


def test_from_yaml_obj_missing_metadata_is_allowed():
  obj = {'apiVersion': 'batch/v1', 'kind': 'Job'}
  k = K8sInfo.from_yaml_obj(obj)
  assert k.api_version == 'batch/v1'
  assert k.group == 'batch'
  assert k.version == 'v1'
  assert k.kind == 'Job'
  assert k.name is None
  assert k.namespace is None


def test_from_yaml_obj_metadata_without_name_namespace():
  obj = {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'labels': {'app': 'x'}}}
  k = K8sInfo.from_yaml_obj(obj)
  assert k.api_version == 'v1'
  assert k.group is None
  assert k.version == 'v1'
  assert k.kind == 'Service'
  assert k.name is None
  assert k.namespace is None


def test_from_yaml_obj_non_dict_returns_all_none():
  assert K8sInfo.from_yaml_obj('not-a-dict') == K8sInfo(None, None, None, None, None, None)
  assert K8sInfo.from_yaml_obj(123) == K8sInfo(None, None, None, None, None, None)
  assert K8sInfo.from_yaml_obj(['kind', 'Deployment']) == K8sInfo(None, None, None, None, None, None)


def test_from_yaml_obj_ignores_non_string_fields():
  obj = {
    'apiVersion': 42,
    'kind': ['Deployment'],
    'metadata': {'name': {'x': 1}, 'namespace': 7},
  }
  k = K8sInfo.from_yaml_obj(obj)
  assert k.api_version is None
  assert k.kind is None
  assert k.name is None
  assert k.namespace is None
  assert k.group is None
  assert k.version is None


def test_from_yaml_obj_group_version_split_with_weird_chars():
  obj = {'apiVersion': 'weird.group/v2beta@1', 'kind': 'CustomThing', 'metadata': {'name': 'm'}}
  k = K8sInfo.from_yaml_obj(obj)
  # We only split on the first '/', rest stays in 'version'
  assert k.group == 'weird.group'
  assert k.version == 'v2beta@1'
  assert k.kind == 'CustomThing'
  assert k.name == 'm'


##################
### SourceInfo.from_source_path
##################

def test_from_source_path__simple_yaml_in_dir():
  si = SourceInfo.from_source_path('app/deploy.yml')
  assert si is not None
  assert si.rel_dir == 'app'
  assert si.source_stem == 'deploy'
  assert si.source_ext == '.yml'


def test_from_source_path__templated_yaml_j2():
  si = SourceInfo.from_source_path('app/deploy.yml.j2')
  # '.j2' is removed first, then last extension split
  assert si is not None
  assert si.rel_dir == 'app'
  assert si.source_stem == 'deploy'
  assert si.source_ext == '.yml'


def test_from_source_path__no_extension():
  si = SourceInfo.from_source_path('app/config')
  assert si is not None
  assert si.rel_dir == 'app'
  assert si.source_stem == 'config'
  assert si.source_ext == ''


def test_from_source_path__multi_dot_extension():
  si = SourceInfo.from_source_path('app/archive/file.tar.gz')
  # Only the LAST extension is treated as ext
  assert si is not None
  assert si.rel_dir == 'app/archive'
  assert si.source_stem == 'file.tar'
  assert si.source_ext == '.gz'


def test_from_source_path__root_file_yaml_j2():
  si = SourceInfo.from_source_path('service.yaml.j2')
  assert si is not None
  assert si.rel_dir == '.'
  assert si.source_stem == 'service'
  assert si.source_ext == '.yaml'


def test_from_source_path__root_file_plain():
  si = SourceInfo.from_source_path('service')
  assert si is not None
  assert si.rel_dir == '.'
  assert si.source_stem == 'service'
  assert si.source_ext == ''


def test_from_source_path__hidden_file_dotenv():
  si = SourceInfo.from_source_path('config/.env')
  assert si is not None
  assert si.rel_dir == 'config'
  assert si.source_stem == '.env'
  assert si.source_ext == ''


def test_from_source_path__hidden_file_dotenv_j2():
  si = SourceInfo.from_source_path('config/.env.j2')
  assert si is not None
  assert si.rel_dir == 'config'
  assert si.source_stem == '.env'
  assert si.source_ext == ''


def test_from_source_path__script_j2_without_prior_ext():
  si = SourceInfo.from_source_path('scripts/setup.j2')
  # '.j2' removed -> 'setup' with no extension
  assert si is not None
  assert si.rel_dir == 'scripts'
  assert si.source_stem == 'setup'
  assert si.source_ext == ''


##################
### Pattern.apply
##################

def test_pattern_basic_substitution():
  p = Pattern('{rel_dir}/{kind}_{name}.yml')
  fields = {'rel_dir': 'apps', 'kind': 'deployment', 'name': 'grafana'}
  assert p.apply(fields) == 'apps/deployment_grafana.yml'


def test_pattern_removes_leading_slashes_and_double_slashes():
  p = Pattern('/{rel_dir}//{kind}_{name}.yml')
  fields = {'rel_dir': 'ns', 'kind': 'svc', 'name': 'api'}
  # Leading slash trimmed, // collapsed to /
  assert p.apply(fields) == 'ns/svc_api.yml'


def test_pattern_lowercase_applied_when_enabled():
  p = Pattern('{rel_dir}/{Kind}_{Name}.yml', lower=True)
  fields = {'rel_dir': 'TEST', 'Kind': 'Deployment', 'Name': 'MyApp'}
  assert p.apply(fields) == 'test/deployment_myapp.yml'


def test_pattern_lowercase_disabled():
  p = Pattern('{rel_dir}/{Kind}_{Name}.yml', lower=False)
  fields = {'rel_dir': 'TEST', 'Kind': 'Deployment', 'Name': 'MyApp'}
  assert p.apply(fields) == 'TEST/Deployment_MyApp.yml'


def test_pattern_no_rel_dir_keeps_file_name_only():
  p = Pattern('{rel_dir}/{kind}.yml')
  fields = {'rel_dir': '', 'kind': 'Deployment'}
  assert p.apply(fields) == 'Deployment.yml'


##################
### SourcePolicy
##################

def _src(path: str) -> SourceInfo:
  return SourceInfo.from_source_path(path)


def test_sourcepolicy_basic_yaml():
  pol = SourcePolicy()
  src = _src('app/deploy.yaml')
  out = pol.render(k8s=None, src=src)
  assert out == 'app/deploy.yaml'


def test_sourcepolicy_j2_template_strips_j2():
  pol = SourcePolicy()
  src = _src('ns/service.yml.j2')
  out = pol.render(k8s=None, src=src)
  assert out == 'ns/service.yml'


def test_sourcepolicy_root_file_no_ext():
  pol = SourcePolicy()
  src = _src('README')
  out = pol.render(k8s=None, src=src)
  assert out == 'README'


def test_sourcepolicy_nested_path():
  pol = SourcePolicy()
  src = _src('apps/monitoring/grafana.yaml')
  out = pol.render(k8s=None, src=src)
  assert out == 'apps/monitoring/grafana.yaml'


def test_sourcepolicy_multi_dot_extension():
  pol = SourcePolicy()
  src = _src('pkg/archive/app.tar.gz')
  out = pol.render(k8s=None, src=src)
  assert out == 'pkg/archive/app.tar.gz'


def test_sourcepolicy_hidden_file():
  pol = SourcePolicy()
  src = _src('config/.env')
  out = pol.render(k8s=None, src=src)
  assert out == 'config/.env'


def test_sourcepolicy_hidden_file_j2():
  pol = SourcePolicy()
  src = _src('config/.env.j2')
  out = pol.render(k8s=None, src=src)
  assert out == 'config/.env'


def test_sourcepolicy_lowercase_enabled_by_default_pattern():
  pol = SourcePolicy(pattern=Pattern('{rel_dir}/{source_stem}{source_ext}', lower=True))
  src = _src('APP/FILE.YAML')
  out = pol.render(k8s=None, src=src)
  assert out == 'app/file.yaml'


def test_sourcepolicy_lowercase_disabled():
  pol = SourcePolicy(pattern=Pattern('{rel_dir}/{source_stem}{source_ext}', lower=False))
  src = _src('APP/FILE.YAML')
  out = pol.render(k8s=None, src=src)
  assert out == 'APP/FILE.YAML'


def test_sourcepolicy_custom_pattern_uses_source_fields():
  pol = SourcePolicy(pattern=Pattern('{rel_dir}/src_{source_stem}{source_ext}', lower=True))
  src = _src('svc/api.yaml')
  out = pol.render(k8s=None, src=src)
  assert out == 'svc/src_api.yaml'


##################
### K8sPolicy
##################

def test_k8spolicy_falls_back_when_k8s_is_none():
  pol = K8sPolicy()
  src = _src('apps/cm.yml.j2')
  with pytest.raises(OutputFilenameConstructionError):
    pol.render(k8s=None, src=src)


def test_k8spolicy_falls_back_when_kind_missing():
  pol = K8sPolicy()
  src = _src('svc/service.yaml')
  k = K8sInfo(api_version='v1', kind=None, name='web', namespace='default',
              group=None, version='v1')
  with pytest.raises(OutputFilenameConstructionError):
    pol.render(k8s=k, src=src)


def test_k8spolicy_falls_back_when_name_missing():
  pol = K8sPolicy()
  src = _src('ns/namespace.yaml')
  k = K8sInfo(api_version='v1', kind='Namespace', name=None, namespace=None,
              group=None, version='v1')
  with pytest.raises(OutputFilenameConstructionError):
    pol.render(k8s=k, src=src)



def test_k8spolicy_basic_render_with_defaults_and_normalization():
  pol = K8sPolicy()  # default pattern '{rel_dir}/{kind}_{name}.yml'
  src = _src('apps/DEPLOYMENT.yaml')  # rel_dir='apps'
  k = K8sInfo(api_version='apps/v1', kind='Deployment', name='Grafana', namespace=None,
              group='apps', version='v1')
  out = pol.render(k8s=k, src=src)
  assert out == 'apps/deployment_grafana.yml'


def test_k8spolicy_custom_pattern_uses_namespace_and_source_ext():
  # Custom template includes namespace, name, kind, and preserves original source_ext
  pol = K8sPolicy(pattern=Pattern('{rel_dir}/{namespace}_{name}_{kind}{source_ext}', lower=True))
  src = _src('monitoring/grafana.SPEC.YAML.j2')  # source_ext -> '.YAML'
  k = K8sInfo(api_version='apps/v1', kind='Deployment', name='Grafana', namespace='Kube-System',
              group='apps', version='v1')
  out = pol.render(k8s=k, src=src)
  assert out == 'monitoring/kube-system_grafana_deployment.yaml'


def test_k8spolicy_slugging_of_unusual_chars():
  pol = K8sPolicy(pattern=Pattern('{rel_dir}/{group}_{version}_{kind}_{name}.yml', lower=True))
  src = _src('x/y/z.yaml')
  k = K8sInfo(api_version='weird.group/v2beta@1', kind='Custom-Thing@X', name='My App@123', namespace='demo',
              group='weird.group', version='v2beta@1')
  out = pol.render(k8s=k, src=src)
  assert out == 'x/y/weird.group_v2beta-1_custom-thing-x_my-app-123.yml'


def test_k8spolicy_rel_dir_can_be_empty():
  pol = K8sPolicy()
  src = _src('service.yaml')  # rel_dir=''
  k = K8sInfo(api_version='v1', kind='Service', name='API', namespace='default',
              group=None, version='v1')
  out = pol.render(k8s=k, src=src)
  assert out == 'service_api.yml'


def test_k8spolicy_missing_api_version_becomes_unknown_in_fields():
  # Pattern references api_version to ensure normalization fallback is visible
  pol = K8sPolicy(pattern=Pattern('{rel_dir}/{api_version}_{kind}_{name}.yml', lower=True))
  src = _src('apps/cm.yaml')
  k = K8sInfo(api_version=None, kind='ConfigMap', name='Cfg', namespace='ns',
              group=None, version=None)
  with pytest.raises(OutputFilenameConstructionError):
    pol.render(k8s=k, src=src)


##################
### Deduper
##################

def test_deduper_first_time_seen_returns_same_value():
  d = Deduper()
  assert d.unique('path/file.yaml') == 'path/file.yaml'


def test_deduper_second_time_seen_adds_suffix():
  d = Deduper()
  assert d.unique('test/app.yaml') == 'test/app.yaml'
  assert d.unique('test/app.yaml') == 'test/app_1.yaml'


def test_deduper_third_time_seen_increments_suffix():
  d = Deduper()
  assert d.unique('a/b.yaml') == 'a/b.yaml'
  assert d.unique('a/b.yaml') == 'a/b_1.yaml'
  assert d.unique('a/b.yaml') == 'a/b_2.yaml'


def test_deduper_handles_no_extension():
  d = Deduper()
  assert d.unique('config/start') == 'config/start'
  assert d.unique('config/start') == 'config/start_1'
  assert d.unique('config/start') == 'config/start_2'


def test_deduper_handles_multi_dot_paths():
  d = Deduper()
  assert d.unique('pkg/archive/app.tar.gz') == 'pkg/archive/app.tar.gz'
  assert d.unique('pkg/archive/app.tar.gz') == 'pkg/archive/app.tar_1.gz'
  assert d.unique('pkg/archive/app.tar.gz') == 'pkg/archive/app.tar_2.gz'


def test_deduper_independent_paths_dont_clash():
  d = Deduper()
  assert d.unique('x/a.yaml') == 'x/a.yaml'
  assert d.unique('y/a.yaml') == 'y/a.yaml'  # different path, no conflict
  assert d.unique('x/a.yaml') == 'x/a_1.yaml'
  assert d.unique('y/a.yaml') == 'y/a_1.yaml'
