import os


ROOT_DIR = os.getcwd()
CONFIG_DIR = 'config'
SOURCE_DIR = 'source'
OUTPUT_DIR = 'output'
CONTEXT_DUMPS_DIR = 'context-dumps'
KUSTOMIZE_DIR = 'kustomize'
HELMFILE_DIR = 'helmfile'
TMP_DIR = '.tmp'
LOG_CONFIG_FILE = 'log_config.yml'
VAR_IDENTIFIER = '$'
LOGLEVEL = 'INFO'
MAX_CONCURRENT_APPS = 8
MAX_SUBPROC = os.cpu_count() or 4
MAX_IO = 32

ARGOCD_APPLICATION_CR_TEMPLATE = '''\
  apiVersion: argoproj.io/v1alpha1
  kind: Application
  metadata:
    name: {{ __application.application_name }}
    namespace: {{ argocd.namespace }}
  {% if 'sync_wave' in argocd %}
    annotations:
      argocd.argoproj.io/sync-wave: "{{ argocd.sync_wave }}"
  {% endif %}
  {%- if argocd.finalizers | default([]) %}
    finalizers:
    {{ argocd.finalizers | to_nice_yaml | trim }}
  {%- else %}
    finalizers: []
  {%- endif %}
  spec:
    project: {{ argocd.project }}
    source:
      repoURL: {{ argocd.source.repo_url }}
      targetRevision: {{ argocd.source.target_revision }}
      path: {{ __application.path }}
  {% if 'directory' in argocd.source and 'recurse' in argocd.source.directory %}
      directory:
        recurse: {{ argocd.source.directory.recurse }}
  {% endif %}
    destination:
      server: {{ argocd.destination.server }}
      namespace: {{ argocd.destination.namespace }}
    syncPolicy:
      {{ argocd.sync_policy | default({}) | to_nice_yaml(indent=2) | trim | indent(4) }}
    {%- if argocd.ignoreDifferences | default([]) %}
    ignoreDifferences:
    {{ argocd.ignoreDifferences | default([]) | to_nice_yaml(indent=2) | trim | indent(2) }}
    {%- endif %}
  '''

ARGOCD_DEFAULTS = {
  'namespace': 'argocd',
  'project': 'default',
  'source': {
    'target_revision': 'HEAD',
  },
  'destination': {
    'server': 'https://kubernetes.default.svc',
    'namespace': 'argocd',
  },
}
