import textwrap

from make_argocd_fly.utils import resource_parser

def test_resource_parser_simple():
  resource_yml = '''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_missing_name():
  resource_yml = '''\
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      namespace: monitoring
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', None)

def test_resource_parser_with_comments():
  resource_yml = '''\
    apiVersion: apps/v1
    #kind: DaemonSet
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_leading_comments():
  resource_yml = '''\
    #kind: DaemonSet
    apiVersion: apps/v1
    kind: Deployment
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')

def test_resource_parser_with_comments_and_leading_kind():
  resource_yml = '''\
    kind: Deployment
    #kind: DaemonSet
    apiVersion: apps/v1
    metadata:
    # name: grafana-comment
      #name: grafana-comment
      name: grafana
    '''

  assert resource_parser(textwrap.dedent(resource_yml)) == ('Deployment', 'grafana')
