import logging

from make_argocd_fly.renderer import JinjaRenderer

log = logging.getLogger(__name__)


APPLICATION_RESOUCE_TEMPLATE = \
'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{ _application_name }}
  namespace: {{ _argocd_namespace }}
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: {{ _project }}
  source:
    repoURL: {{ _repo_url }}
    targetRevision: {{ _target_revision }}
    path: {{ _path }}
  destination:
    server: {{ _api_server }}
    namespace: {{ _destination_namespace }}
  syncPolicy:
    automated:
      selfHeal: true
      prune: true
      allowEmpty: true
'''


def generate_application(template_vars: dict) -> str:
    renderer = JinjaRenderer()
    return renderer.render(APPLICATION_RESOUCE_TEMPLATE, template_vars)
