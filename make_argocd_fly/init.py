import logging
import os
import yaml

from make_argocd_fly.source import SourceViewer
from make_argocd_fly.output import OutputRenderer

log = logging.getLogger(__name__)


def read_config(config_file: str) -> dict:
  config = {}
  try:
    with open(config_file) as f:
      config = yaml.safe_load(f.read())
  except FileNotFoundError as error:
    log.error('Config file is missing')
    log.fatal(error)
    raise

  if 'envs' not in config:
    log.error('"envs" variable is missing in the config')
    raise Exception

  return config

def build_source_viewer(root_dir: str, source_dir: str, filter: str = None) -> SourceViewer:
  source_viewer = SourceViewer(os.path.join(root_dir, source_dir))
  source_viewer.build('.')

  return source_viewer

def build_output_renderer(output_dir: str, envs: list, filter: str = None) -> OutputRenderer:
  return OutputRenderer(output_dir, envs)
