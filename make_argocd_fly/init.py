import logging
import os
import yaml

from make_argocd_fly.resource import ResourceViewer, ResourceWriter

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

def build_resource_viewer(root_element_abs_path: str, filter: str = None) -> ResourceViewer:
  source_viewer = ResourceViewer(root_element_abs_path)
  source_viewer.build('.')

  return source_viewer

def build_resource_writer(output_dir_abs_path: str, envs: list, filter: str = None) -> ResourceWriter:
  return ResourceWriter(output_dir_abs_path, envs)
