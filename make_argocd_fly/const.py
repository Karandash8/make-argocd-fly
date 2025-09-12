import os
from enum import Enum


DEFAULT_ROOT_DIR = os.getcwd()
DEFAULT_CONFIG_DIR = 'config'
DEFAULT_SOURCE_DIR = 'source'
DEFAULT_OUTPUT_DIR = 'output'
DEFAULT_TMP_DIR = '.tmp'
DEFAULT_LOG_CONFIG_FILE = 'log_config.yml'
DEFAULT_VAR_IDENTIFIER = '$'
DEFAULT_LOGLEVEL = 'INFO'

KEYWORK_ENVS = 'envs'
KEYWORK_APPS = 'apps'
KEYWORK_VARS = 'vars'
KEYWORK_PARAMS = 'params'

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


# TODO: should this be an Enum?
class ParamNames:
  PARENT_APP = 'parent_app'
  PARENT_APP_ENV = 'parent_app_env'
  NON_K8S_FILES_TO_RENDER = 'non_k8s_files_to_render'
  EXCLUDE_RENDERING = 'exclude_rendering'

  @classmethod
  def get_names(cls) -> list[str]:
    return [getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))]


# DEPRECATED
class AppParamsNames:
  APP_DEPLOYER = 'app_deployer'
  APP_DEPLOYER_ENV = 'app_deployer_env'
  NON_K8S_FILES_TO_RENDER = 'non_k8s_files_to_render'
  EXCLUDE_RENDERING = 'exclude_rendering'

  @classmethod
  def get_names(cls) -> list[str]:
    return [getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))]


class ApplicationType(Enum):
  K8S_SIMPLE = 'k8s_simple'
  K8S_KUSTOMIZE = 'k8s_kustomize'
  K8S_APP_OF_APPS = 'k8s_app_of_apps'
