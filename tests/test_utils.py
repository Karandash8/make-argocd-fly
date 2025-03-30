import logging
import pytest
import textwrap

from make_argocd_fly.utils import extract_single_resource, merge_dicts, VarsResolver, FilePathGenerator, get_module_name, \
  get_package_name, build_path, extract_undefined_variable
from make_argocd_fly.exceptions import InternalError, UnknownJinja2Error

###################
### FilePathGenerator
###################

def test_FilePathGenerator__init__():
  resource_yml = 'resource_yml'
  source_file_rel_path = 'path/file.yml'

  generator = FilePathGenerator(resource_yml, source_file_rel_path)

  assert generator.resource_yml == resource_yml
  assert generator.source_file_rel_path == source_file_rel_path

###################
### FilePathGenerator._extract_kind
###################

def test_FilePathGenerator___extract_kind__from_yaml_empty():
  resource_yml = textwrap.dedent('''\
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_kind(resource_yml) == None

def test_FilePathGenerator___extract_kind__from_yaml_simple():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_kind(resource_yml) == 'Deployment'

def test_FilePathGenerator___extract_kind__from_yaml_missing_kind():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_kind(resource_yml) == None

def test_FilePathGenerator___extract_kind__from_yaml_with_comments():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    #kind: DaemonSet
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_kind(resource_yml) == 'Deployment'

def test_FilePathGenerator___extract_kind__from_yaml_with_leading_comments():
  resource_yml = textwrap.dedent('''\
    #kind: DaemonSet
    apiVersion: apps/v1
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_kind(resource_yml) == 'Deployment'

def test_FilePathGenerator___extract_kind__from_yaml_with_comments_and_leading_kind():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    #kind: DaemonSet
    apiVersion: apps/v1
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_kind(resource_yml) == 'Deployment'

def test_FilePathGenerator___extract_kind__from_yaml_with_extra_spaces():
  resource_yml = textwrap.dedent('''\
      kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_kind(resource_yml) == None

###################
### FilePathGenerator._extract_api_version
###################

def test_FilePathGenerator___extract_api_version__from_yaml_empty():
  resource_yml = textwrap.dedent('''\
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_api_version(resource_yml) == None

def test_FilePathGenerator___extract_api_version__from_yaml_simple():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_api_version(resource_yml) == 'apps/v1'

def test_FilePathGenerator___extract_api_version__from_yaml_missing_api_verion():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    metadata:
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_api_version(resource_yml) == None

def test_FilePathGenerator___extract_api_version__from_yaml_with_comments():
  resource_yml = textwrap.dedent('''\
    # apiVersion: apps/v2
    apiVersion: apps/v1
    #kind: DaemonSet
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_api_version(resource_yml) == 'apps/v1'

def test_FilePathGenerator___extract_api_version__from_yaml_with_leading_comments():
  resource_yml = textwrap.dedent('''\
    #kind: DaemonSet
    # apiVersion: apps/v2
    apiVersion: apps/v1
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_api_version(resource_yml) == 'apps/v1'

def test_FilePathGenerator___extract_api_version__from_yaml_with_comments_and_leading_api_version():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    # apiVersion: apps/v2
    kind: Deployment
    #kind: DaemonSet
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_api_version(resource_yml) == 'apps/v1'

def test_FilePathGenerator___extract_api_version__from_yaml_with_extra_spaces():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
      apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_api_version(resource_yml) == None

###################
### FilePathGenerator._extract_name
###################

def test_FilePathGenerator___extract_name__from_yaml_empty():
  resource_yml = textwrap.dedent('''\
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == None

def test_FilePathGenerator___extract_name__from_yaml_simple():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_missing_name():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      namespace: monitoring
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == None

def test_FilePathGenerator___extract_name__from_yaml_with_comments():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    #kind: DaemonSet
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_leading_comments():
  resource_yml = textwrap.dedent('''\
    #kind: DaemonSet
    apiVersion: apps/v1
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_messed_up_order_metadata_at_the_beginning():
  resource_yml = textwrap.dedent('''\
    metadata:
      name: grafana
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_messed_up_order_metadata_in_the_middle():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_extra_spaces():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
        name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == None

def test_FilePathGenerator___extract_name__from_yaml_with_messed_up_order_name_is_not_first():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_messed_up_order_name_is_not_first_with_comment_1():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
    # comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_messed_up_order_name_is_not_first_with_comments_2():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
     # comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_messed_up_order_name_is_not_first_with_comments_3():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
      # comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

def test_FilePathGenerator___extract_name__from_yaml_with_messed_up_order_name_is_not_first_with_comments_4():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      namespace: monitoring
       # comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_name(resource_yml) == 'grafana'

###################
### FilePathGenerator._extract_namespace
###################

def test_FilePathGenerator___extract_namespace__from_yaml_empty():
  resource_yml = textwrap.dedent('''\
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == None

def test_FilePathGenerator___extract_namespace__from_yaml_simple():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: grafana
      namespace: monitoring
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_missing_namespace():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == None

def test_FilePathGenerator___extract_namespace__from_yaml_with_comments():
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    #kind: DaemonSet
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
      # namespace: monitoring-comment
      namespace: monitoring
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_leading_comments():
  resource_yml = textwrap.dedent('''\
    #kind: DaemonSet
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      # namespace: monitoring-comment
      namespace: monitoring
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_messed_up_order_metadata_at_the_beginning():
  resource_yml = textwrap.dedent('''\
    metadata:
      namespace: monitoring
      name: grafana
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
      namespace: notmonitoring
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_messed_up_order_metadata_in_the_middle():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
      namespace: notmonitoring
    metadata:
      name: grafana
      namespace: monitoring
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_extra_spaces():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
      namespace: notmonitoring
    metadata:
      name: grafana
        namespace: monitoring
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == None

def test_FilePathGenerator___extract_namespace__from_yaml_with_messed_up_order_name_is_not_first():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      name: grafana
      namespace: monitoring
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_messed_up_order_name_is_not_first_with_comment_1():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
    # comment
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_messed_up_order_name_is_not_first_with_comments_2():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
     # comment
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_messed_up_order_name_is_not_first_with_comments_3():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
      # comment
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

def test_FilePathGenerator___extract_namespace__from_yaml_with_messed_up_order_name_is_not_first_with_comments_4():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    stringData:
      name: notgrafana
    metadata:
       # comment
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None)._extract_namespace(resource_yml) == 'monitoring'

###################
### FilePathGenerator._extract_file_rel_path
###################

def test_FilePathGenerator___extract_file_rel_path__from_empty():
  source_file_rel_path = ''

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_rel_path(source_file_rel_path) == None

def test_FilePathGenerator___extract_file_rel_path__from_file():
  source_file_rel_path = 'file.txt'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_rel_path(source_file_rel_path) == None

def test_FilePathGenerator___extract_file_rel_path__from_path():
  source_file_rel_path = 'path/path/'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_rel_path(source_file_rel_path) == 'path/path'

def test_FilePathGenerator___extract_file_rel_path__from_file_path():
  source_file_rel_path = 'path/file.txt'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_rel_path(source_file_rel_path) == 'path'

###################
### FilePathGenerator._extract_source_file_name
###################

def test_FilePathGenerator___extract_source_file_name__from_empty():
  source_file_rel_path = ''

  assert FilePathGenerator(None, source_file_rel_path)._extract_source_file_name(source_file_rel_path) == None

def test_FilePathGenerator___extract_source_file_name__from_file():
  source_file_rel_path = 'file.txt'

  assert FilePathGenerator(None, source_file_rel_path)._extract_source_file_name(source_file_rel_path) == 'file'

def test_FilePathGenerator___extract_source_file_name__from_j2_file():
  source_file_rel_path = 'file.txt.j2'

  assert FilePathGenerator(None, source_file_rel_path)._extract_source_file_name(source_file_rel_path) == 'file'

def test_FilePathGenerator___extract_source_file_name__from_file_multi_ext():
  source_file_rel_path = 'file.txt.txt'

  assert FilePathGenerator(None, source_file_rel_path)._extract_source_file_name(source_file_rel_path) == 'file.txt'

def test_FilePathGenerator___extract_source_file_name__from_file_no_ext():
  source_file_rel_path = 'file'

  assert FilePathGenerator(None, source_file_rel_path)._extract_source_file_name(source_file_rel_path) == 'file'

def test_FilePathGenerator___extract_source_file_name__from_file_path():
  source_file_rel_path = 'path/file.txt'

  assert FilePathGenerator(None, source_file_rel_path)._extract_source_file_name(source_file_rel_path) == 'file'

def test_FilePathGenerator___extract_source_file_name__from_path():
  source_file_rel_path = 'path/'

  assert FilePathGenerator(None, source_file_rel_path)._extract_source_file_name(source_file_rel_path) == None

###################
### FilePathGenerator._extract_file_extension
###################

def test_FilePathGenerator___extract_file_extension__from_empty():
  source_file_rel_path = ''

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_extension(source_file_rel_path) == None

def test_FilePathGenerator___extract_file_extension__from_file():
  source_file_rel_path = 'file.txt'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_extension(source_file_rel_path) == '.txt'

def test_FilePathGenerator___extract_file_extension__from_j2_file():
  source_file_rel_path = 'file.txt.j2'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_extension(source_file_rel_path) == '.txt'

def test_FilePathGenerator___extract_file_extension__from_file_multi_ext():
  source_file_rel_path = 'file.txt.log'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_extension(source_file_rel_path) == '.log'

def test_FilePathGenerator___extract_file_extension__from_file_no_ext():
  source_file_rel_path = 'file'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_extension(source_file_rel_path) == None

def test_FilePathGenerator___extract_file_extension__from_file_path():
  source_file_rel_path = 'path/file.txt'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_extension(source_file_rel_path) == '.txt'

def test_FilePathGenerator___extract_file_extension__from_path():
  source_file_rel_path = 'path/'

  assert FilePathGenerator(None, source_file_rel_path)._extract_file_extension(source_file_rel_path) == None

###################
### FilePathGenerator.generate_from_source_file
###################

def test_FilePathGenerator__generate_from_source_file_path__without_source_file(caplog):
  caplog.set_level(logging.DEBUG)
  source_file_rel_path = 'path/'

  generator = FilePathGenerator(None, source_file_rel_path)

  with pytest.raises(ValueError):
    generator.generate_from_source_file()
  assert 'Filename cannot be constructed' in caplog.text

def test_FilePathGenerator__generate_from_source_file_path__from_source_file():
  source_file_rel_path = 'file'

  assert FilePathGenerator(None, source_file_rel_path).generate_from_source_file() == 'file'

def test_FilePathGenerator__generate_from_source_file_path__from_j2_source_file():
  source_file_rel_path = 'file.j2'

  assert FilePathGenerator(None, source_file_rel_path).generate_from_source_file() == 'file'

def test_FilePathGenerator__generate_from_source_file_path__from_source_file_with_ext():
  source_file_rel_path = 'file.txt'

  assert FilePathGenerator(None, source_file_rel_path).generate_from_source_file() == 'file.txt'

def test_FilePathGenerator__generate_from_source_file_path__from_j2_source_file_with_ext():
  source_file_rel_path = 'file.txt.j2'

  assert FilePathGenerator(None, source_file_rel_path).generate_from_source_file() == 'file.txt'

def test_FilePathGenerator__generate_from_source_file_path__from_source_file_with_path():
  source_file_rel_path = 'path/file.txt'

  assert FilePathGenerator(None, source_file_rel_path).generate_from_source_file() == 'path/file.txt'

def test_FilePathGenerator__generate_from_source_file_path__from_j2_source_file_with_path():
  source_file_rel_path = 'path/file.txt.j2'

  assert FilePathGenerator(None, source_file_rel_path).generate_from_source_file() == 'path/file.txt'

###################
### FilePathGenerator.generate_from_k8s_resource
###################

def test_FilePathGenerator__generate_from_k8s_resource__from_empty(caplog):
  caplog.set_level(logging.DEBUG)
  resource_yml = textwrap.dedent('''\
    ''')

  generator = FilePathGenerator(resource_yml, None)

  with pytest.raises(ValueError):
    generator.generate_from_k8s_resource()
  assert 'Filename cannot be constructed' in caplog.text

def test_FilePathGenerator__generate_from_k8s_resource__missing_resource_kind(caplog):
  caplog.set_level(logging.DEBUG)
  resource_yml = textwrap.dedent('''\
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')

  generator = FilePathGenerator(resource_yml, None)

  with pytest.raises(ValueError):
    generator.generate_from_k8s_resource()
  assert 'Filename cannot be constructed' in caplog.text

def test_FilePathGenerator__generate_from_k8s_resource__missing_resource_name():
  resource_yml = textwrap.dedent('''\
    kind: Kustomization
    apiVersion: apps/v1
    data:
      namespace: monitoring
    ''')

  assert FilePathGenerator(resource_yml, None).generate_from_k8s_resource() == 'kustomization.yml'

def test_FilePathGenerator__generate_from_k8s_resource__simple():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')

  assert FilePathGenerator(resource_yml, None).generate_from_k8s_resource() == 'deployment_grafana.yml'

def test_FilePathGenerator__generate_from_k8s_resource__with_rel_path():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')
  source_file_rel_path = 'path/'

  assert FilePathGenerator(resource_yml, source_file_rel_path).generate_from_k8s_resource() == 'path/deployment_grafana.yml'

def test_FilePathGenerator__generate_from_k8s_resource__with_rel_path_2():
  resource_yml = textwrap.dedent('''\
    kind: Deployment
    apiVersion: apps/v1
    metadata:
      namespace: monitoring
      name: grafana
    ''')
  source_file_rel_path = 'path/file.txt'

  assert FilePathGenerator(resource_yml, source_file_rel_path).generate_from_k8s_resource() == 'path/deployment_grafana.yml'

###################
### extract_single_resource
###################

def test_extract_single_resource_with_valid_yaml():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('kind: Deployment\nmetadata:\n  name: grafana'),
      ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_extra_separator_at_the_top():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    ---
    kind: Deployment
    metadata:
      name: grafana
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('kind: Deployment\nmetadata:\n  name: grafana'),
      ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_extra_separator_at_the_bottom():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    ---
    '''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('kind: Deployment\nmetadata:\n  name: grafana'),
      ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_single_yaml_extra_separator_at_the_bottom():
  multi_resource_yml = '''\
    kind: DaemonSet
    metadata:
      name: prometheus
    ---
    '''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_single_yaml_extra_separator_at_the_bottom_without_new_line():
  multi_resource_yml = '''\
    kind: DaemonSet
    metadata:
      name: prometheus
    ---'''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_not_an_extra_separator():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
      comment: "--- This is not an extra separator"
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('kind: Deployment\nmetadata:\n  name: grafana\n  comment: "--- This is not an extra separator"'),
      ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

def test_extract_single_resource_with_valid_yaml_not_an_extra_separator_2():
  # Test when valid YAML is provided with multiple resources
  multi_resource_yml = '''\
    kind: Deployment
    metadata:
      name: grafana
      comment: |
        This is not an extra separator ----
    ---
    kind: DaemonSet
    metadata:
      name: prometheus
    '''

  result = list(extract_single_resource(textwrap.dedent(multi_resource_yml)))
  expected = [
      ('kind: Deployment\nmetadata:\n  name: grafana\n  comment: |\n    This is not an extra separator ----'),
      ('kind: DaemonSet\nmetadata:\n  name: prometheus')
  ]

  assert result == expected

###############
### merge_dicts
###############

def test_merge_dicts_non_nested():
    # Test merging two dictionaries with non-nested keys
    dict1 = {'a': 1, 'b': 2}
    dict2 = {'b': 3, 'c': 4}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': 3, 'c': 4}

def test_merge_dicts_nested():
    # Test merging dictionaries with nested keys
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
    dict2 = {'b': {'c': 4, 'e': 5}, 'f': 6}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': {'c': 4, 'd': 3, 'e': 5}, 'f': 6}

def test_merge_dicts_empty_left():
    # Test merging dictionaries with an empty dictionary on the left
    dict1 = {}
    dict2 = {'a': 1, 'b': 2}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': 2}

def test_merge_dicts_empty_right():
    # Test merging dictionaries with an empty dictionary on the right (should keep the dictionary on the left)
    dict1 = {'a': 1, 'b': 2}
    dict2 = {}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': 2}

def test_merge_dicts_both_empty():
    # Test merging two empty dictionaries
    dict1 = {}
    dict2 = {}
    result = merge_dicts(dict1, dict2)
    assert result == {}

def test_merge_dicts_empty_dict_on_right():
    # Test merging dictionaries with an empty dictionary on the right (should make it an empty dictionary on the left)
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
    dict2 = {'b': {}, 'f': None, 'g': 7}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'b': {}, 'f': None, 'g': 7}

def test_merge_dicts_none_value_on_right():
    # Test merging dictionaries with a None value on the right (should delete the key on the left)
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3}}
    dict2 = {'b': None, 'f': 6}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': 1, 'f': 6}

def test_merge_dicts_empty_dict_and_none_value():
    # Test merging dictionaries with a mix of empty dictionary and None value (should behave accordingly)
    dict1 = {'a': {}, 'b': None, 'c': 3}
    dict2 = {'a': {'x': 1}, 'b': 2, 'd': {}}
    result = merge_dicts(dict1, dict2)
    assert result == {'c': 3, 'a': {'x': 1}, 'b': 2, 'd': {}}

def test_merge_dicts_nested_dicts():
    # Test merging dictionaries with nested dictionaries
    dict1 = {'a': {'b': {'c': 1, 'd': 2}}, 'e': 3}
    dict2 = {'a': {'b': {'d': 4, 'e': 5}}, 'f': 6}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': {'b': {'c': 1, 'd': 4, 'e': 5}}, 'e': 3, 'f': 6}

def test_merge_dicts_empty_nested_dict_on_right():
    # Test merging dictionaries with an empty nested dictionary on the right (should make it empty on the left)
    dict1 = {'a': {'b': {'c': 1, 'd': 2}}}
    dict2 = {'a': {'b': {}}}
    result = merge_dicts(dict1, dict2)
    assert result == {'a': {'b': {}}}

def test_merge_dicts_three_dicts():
    # Test merging three dictionaries with various corner cases
    dict1 = {'a': 1, 'b': 2, 'c': {'x': 10, 'y': 20}}
    dict2 = {'b': 3, 'c': {'x': 30, 'z': 40}, 'd': 4}
    dict3 = {'c': {'z': 300, 'w': 400}, 'e': 5}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # 'a' and 'd' keys from dict1, 'e' key from dict3, and 'w' key from dict3 should be in the result
    # 'b' key should take the value from dict2, 'c' key should merge values from all dictionaries
    assert result == {'a': 1, 'b': 3, 'c': {'x': 30, 'y': 20, 'z': 300, 'w': 400}, 'd': 4, 'e': 5}

def test_merge_dicts_three_empty_dicts():
    # Test merging three empty dictionaries
    dict1 = {}
    dict2 = {}
    dict3 = {}

    # Merging three empty dictionaries should result in an empty dictionary
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {}

def test_merge_dicts_three_nested_dicts():
    # Test merging three dictionaries with nested dictionaries
    dict1 = {'a': {'x': 1, 'y': {'z': 2}}}
    dict2 = {'a': {'y': {'z': 3, 'w': 4}}}
    dict3 = {'a': {'w': 5, 'u': {'v': 6}}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # Merged dictionaries should contain all keys and nested dictionaries
    assert result == {'a': {'x': 1, 'y': {'z': 3, 'w': 4}, 'w': 5, 'u': {'v': 6}}}

def test_merge_dicts_three_empty_nested_dict():
    # Test merging three dictionaries with empty nested dictionaries
    dict1 = {'a': {}}
    dict2 = {'a': {'x': 1}}
    dict3 = {'a': {'y': 2, 'z': {}}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # Merged dictionaries should contain empty nested dictionary
    assert result == {'a': {'x': 1, 'y': 2, 'z': {}}}

def test_merge_dicts_three_dicts_with_none():
    # Test merging three dictionaries with various scenarios involving None values
    dict1 = {'a': 1, 'b': 2, 'c': {'x': 10, 'y': 20}}
    dict2 = {'b': 3, 'c': {'x': None, 'z': 40}, 'd': None}
    dict3 = {'c': {'z': 300, 'w': 400}, 'e': None}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # 'a', 'd', and 'e' keys from dict1, 'd' key from dict2 should be removed
    # 'b' key should take the value from dict2, 'c' key should merge values from all dictionaries
    assert result == {'a': 1, 'b': 3, 'c': {'y': 20, 'z': 300, 'w': 400}, 'd': None, 'e': None}

def test_merge_dicts_three_nested_dicts_with_none():
    # Test merging three dictionaries with nested dictionaries containing None values
    dict1 = {'a': {'x': 1, 'y': {'z': 2, 'w': None}}}
    dict2 = {'a': {'y': {'z': 3, 'w': 4, 'v': None}}}
    dict3 = {'a': {'w': 5, 'u': {'v': 6, 'x': None}}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # None values should override other values in the merged dictionaries
    assert result == {'a': {'x': 1, 'y': {'z': 3, 'w': 4, 'v': None}, 'w': 5, 'u': {'v': 6, 'x': None}}}

def test_merge_dicts_three_none_values():
    # Test merging three dictionaries with None values
    dict1 = {'a': None, 'b': {'x': None, 'y': 20}}
    dict2 = {'b': None, 'c': None, 'd': 4}
    dict3 = {'c': None, 'e': None}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # All keys with None values should be removed
    assert result == {'a': None, 'd': 4, 'e': None}

def test_merge_dicts_three_dicts_with_empty_nested():
    # Test merging three dictionaries with empty nested dictionaries
    dict1 = {'a': {'b': {}}, 'c': {'d': 1}}
    dict2 = {'a': {'b': {}}, 'c': {'d': 2}}
    dict3 = {'a': {'b': {}}, 'c': {'d': 3}}

    # Merging dict1, dict2, and dict3
    result = merge_dicts(dict1, dict2, dict3)

    # Merged dictionaries should contain empty nested dictionaries
    assert result == {'a': {'b': {}}, 'c': {'d': 3}}

def test_merge_dicts_non_nested_and_nested_keys_with_none():
    # Test merging dictionaries with non-nested and nested keys, and None values
    dict1 = {'a': 1, 'b': {'c': 2, 'd': 3, 'e': None}}
    dict2 = {'b': {'c': 4, 'e': 5, 'f': None}, 'g': 6}
    dict3 = {'h': None, 'i': {'j': 7, 'k': None}}
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {'a': 1, 'b': {'c': 4, 'd': 3, 'e': 5, 'f': None}, 'g': 6, 'h': None, 'i': {'j': 7, 'k': None}}

def test_merge_dicts_deeply_nested_keys():
    # Test merging dictionaries with deeply nested keys
    dict1 = {'a': {'b': {'c': {'d': {'e': 1}}}}}
    dict2 = {'a': {'b': {'c': {'d': {'f': 2}}}}}
    dict3 = {'a': {'b': {'c': {'d': {'g': 3}}}}}
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {'a': {'b': {'c': {'d': {'e': 1, 'f': 2, 'g': 3}}}}}

def test_merge_dicts_empty_nested_and_none_values():
    # Test merging dictionaries with empty nested dictionaries and None values
    dict1 = {'a': {'b': {}}, 'c': {'d': 1, 'e': None}}
    dict2 = {'a': {'b': {'f': None}}, 'c': {'d': 2, 'e': 3}}
    dict3 = {'a': {'b': {'g': None}}, 'c': {'d': None, 'h': 4}}
    result = merge_dicts(dict1, dict2, dict3)
    assert result == {'a': {'b': {'f': None, 'g': None}}, 'c': {'e': 3, 'h': 4}}

################
### VarsResolver
################

def test_vars_resolver_empty_vars():
  resolver = VarsResolver()
  vars = {}
  result = resolver.resolve(vars, vars)
  assert result == {}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_single_var():
  resolver = VarsResolver()
  vars = {'var1': 'value1'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value1'}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_multiple_vars():
  resolver = VarsResolver()
  vars = {'var1': 'value1', 'var2': 'value2', 'var3': 'value3'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value1', 'var2': 'value2', 'var3': 'value3'}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_nested_vars():
  resolver = VarsResolver()
  vars = {'var1': 'value1', 'var2': {'var3': 'value3'}}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value1', 'var2': {'var3': 'value3'}}
  assert resolver.get_resolutions() == 0

def test_vars_resolver_var_with_resolvable_var():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': 'value2'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2', 'var2': 'value2'}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_multiple_resolvable_var_with_concat():
  resolver = VarsResolver()
  vars = {'var1': '${var2}/${var3}', 'var2': 'value2', 'var3': 'value3'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2/value3', 'var2': 'value2', 'var3': 'value3'}
  assert resolver.get_resolutions() == 2

def test_vars_resolver_var_with_resolvable_var_with_concat_left():
  resolver = VarsResolver()
  vars = {'var1': ' ${var2}', 'var2': 'value2'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': ' value2', 'var2': 'value2'}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_resolvable_var_with_concat_right():
  resolver = VarsResolver()
  vars = {'var1': '${var2} ', 'var2': 'value2'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2 ', 'var2': 'value2'}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_multiple_resolvable_vars():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': 'value2', 'var3': '${var4}', 'var4': 'value4'}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value2', 'var2': 'value2', 'var3': 'value4', 'var4': 'value4'}
  assert resolver.get_resolutions() == 2

def test_vars_resolver_value_with_unresolvable_var(caplog):
  resolver = VarsResolver()
  vars = {'var1': '${var2}'}
  with pytest.raises(KeyError):
    resolver.resolve(vars, vars)
  assert 'Variable ${var2} not found in vars' in caplog.text

def test_vars_resolver_var_with_resolvable_var_dict():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': {'var3': 'value3'}}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': {'var3': 'value3'}, 'var2': {'var3': 'value3'}}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_resolvable_var_list():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': ['value2']}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': ['value2'], 'var2': ['value2']}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_with_nested_resolvable_vars():
  resolver = VarsResolver()
  vars = {'var1': '${var2}', 'var2': '${var3}', 'var3': 'value3'}
  result = VarsResolver().resolve_all(vars, vars)
  assert result == {'var1': 'value3', 'var2': 'value3', 'var3': 'value3'}

def test_vars_resolver_var_with_resolvable_var_complex_key():
  resolver = VarsResolver()
  vars = {'var1': '${var2[var3]}', 'var2': {'var3': 'value3'}}
  result = resolver.resolve(vars, vars)
  assert result == {'var1': 'value3', 'var2': {'var3': 'value3'}}
  assert resolver.get_resolutions() == 1

def test_vars_resolver_var_from_different_source():
  resolver = VarsResolver()
  vars = {'var1': '${var2}'}
  vars_source ={'var2': 'value2'}
  result = resolver.resolve(vars, vars_source)
  assert result == {'var1': 'value2'}
  assert resolver.get_resolutions() == 1

################
### get_module_name
################

def test__get_module_name():
  assert get_module_name() == 'make_argocd_fly'

################
### get_package_name
################

def test__get_package_name():
  assert get_package_name() == 'make-argocd-fly'

################
### build_path
################

def test_build_path_with_relative_path_in_current_directory(tmp_path):
  root_dir = tmp_path
  path = 'config.py'
  expected = tmp_path / 'config.py'
  expected.write_text('test')

  assert build_path(root_dir, path) == str(expected)

def test_build_path_with_absolute_path_in_current_directory(tmp_path):
  root_dir = tmp_path
  path = tmp_path / 'config.py'
  expected = tmp_path / 'config.py'
  expected.write_text('test')

  assert build_path(root_dir, path) == expected

def test_build_path_with_relative_path_in_subdirectory(tmp_path):
  root_dir = tmp_path
  src_dir = tmp_path / 'source'
  src_dir.mkdir()
  path = 'source/app.py'
  expected = tmp_path / 'source/app.py'
  expected.write_text('test')

  assert build_path(str(root_dir), path) == str(expected)

def test_build_path_with_absolute_path_in_subdirectory(tmp_path):
  root_dir = tmp_path
  src_dir = tmp_path / 'source'
  src_dir.mkdir()
  path = tmp_path / 'source/app.py'
  expected = tmp_path / 'source/app.py'
  expected.write_text('test')

  assert build_path(root_dir, path) == expected

def test_build_path_with_empty_path(tmp_path, caplog):
  root_dir = tmp_path
  path = ''

  with pytest.raises(InternalError):
    build_path(root_dir, path)
  assert 'Path is empty' in caplog.text

def test_build_path_with_none_path(tmp_path, caplog):
  root_dir = tmp_path
  path = None

  with pytest.raises(InternalError):
    build_path(root_dir, path)
  assert 'Path is empty' in caplog.text

def test_build_path_with_nonexistent_path(tmp_path, caplog):
  root_dir = str(tmp_path)
  path = 'nonexistent_file.py'
  non_existent_path = tmp_path / 'nonexistent_file.py'

  with pytest.raises(InternalError):
    build_path(root_dir, path)
  assert 'Path does not exist: {}'.format(non_existent_path) in caplog.text

def test_build_path_with_nonexistent_path_allow_missing(tmp_path, caplog):
  root_dir = str(tmp_path)
  path = 'nonexistent_file.py'
  non_existent_path = tmp_path / 'nonexistent_file.py'

  assert build_path(root_dir, path, allow_missing=True) == str(non_existent_path)

################
### extract_undefined_variable
################

def test_extract_undefined_variable__jinja2_variable():
  variable_name = 'test_variable'
  message = '\'{}\' is undefined'.format(variable_name)

  assert extract_undefined_variable(message) == variable_name

def test_extract_undefined_variable__jinja2_attribute():
  variable_name = 'test_attribute'
  message = 'has no attribute \'{}\''.format(variable_name)

  assert extract_undefined_variable(message) == variable_name

def test_extract_undefined_variable__exception():
  message = 'random message'

  with pytest.raises(UnknownJinja2Error):
    extract_undefined_variable(message)
