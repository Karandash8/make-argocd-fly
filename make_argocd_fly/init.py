import logging
import os
import yaml

from make_argocd_fly.resource import ResourceViewer, ResourceWriter
from make_argocd_fly.config import Config
from make_argocd_fly.utils import extract_dir_rel_path, multi_resource_parser

log = logging.getLogger(__name__)


def read_config(root_dir: str, config_file: str) -> Config:
  config = {}
  try:
    with open(os.path.join(root_dir, config_file)) as f:
      config = yaml.safe_load(f.read())
  except FileNotFoundError as error:
    log.error('Config file is missing')
    log.fatal(error)
    raise

  return Config(root_dir, config)

def build_resource_viewer(root_element_abs_path: str, filter: str = None) -> ResourceViewer:
  source_viewer = ResourceViewer(root_element_abs_path)
  source_viewer.build('.')

  return source_viewer

def build_resource_writer(output_dir_abs_path: str, envs: list, filter: str = None) -> ResourceWriter:
  existing_resources = {}

  if os.path.exists(output_dir_abs_path):
    output_viewer = build_resource_viewer(output_dir_abs_path)
    yml_children = output_viewer.get_files_children('.yml$')
    existing_resources = {(extract_dir_rel_path(yml_child.element_rel_path), resource_kind, resource_name): resource_yml
                         for yml_child in yml_children for resource_kind, resource_name, resource_yml in multi_resource_parser(yml_child.content)}

  return ResourceWriter(output_dir_abs_path, envs, existing_resources)
