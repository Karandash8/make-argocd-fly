import logging
import logging.config
import yaml
import os
import argparse
import subprocess
import shutil
from jinja2 import Environment, FileSystemLoader

from make_argocd_fly.config import read_config, Config
from make_argocd_fly.utils import extract_dir_rel_path, multi_resource_parser, resource_parser
from make_argocd_fly.resource import build_resource_viewer, build_resource_writer, ResourceViewer, ResourceWriter

LOG_CONFIG_FILE = 'log_config.yml'
CONFIG_FILE = 'config.yml'

try:
  with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), LOG_CONFIG_FILE)) as f:
    yaml_config = yaml.safe_load(f.read())
    logging.config.dictConfig(yaml_config)
except FileNotFoundError:
  logging.basicConfig(level='DEBUG')

log = logging.getLogger(__name__)


def step_1(viewer: ResourceViewer, writer: ResourceWriter, config: Config) -> None:
  # step 1: copy .yml files, render .j2 files
  environment = Environment(loader=FileSystemLoader(viewer.root_element_abs_path))
  apps = [app for app in viewer.get_dirs_children(depth=1)]
  for app in apps:
    yml_children = viewer.get_child(app.name).get_files_children('.yml$')
    j2_children = viewer.get_child(app.name).get_files_children('.j2$')
    log.debug('app: {}, yml files: {}, j2_files: {}'.format(app.name, [child.element_rel_path for child in yml_children], [child.element_rel_path for child in j2_children]))

    for yml_child in yml_children:
      dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
      for resource_kind, resource_name, resource_yml in multi_resource_parser(yml_child.content):
        writer.update_resource(dir_rel_path, resource_kind, resource_name, resource_yml)

    for j2_child in j2_children:
      dir_rel_path = extract_dir_rel_path(j2_child.element_rel_path)
      template = environment.get_template(j2_child.element_rel_path)
      for resource_kind, resource_name, resource_yml in multi_resource_parser(template.render(config.vars)):
        writer.update_resource(dir_rel_path, resource_kind, resource_name, resource_yml)

def step_2(viewer: ResourceViewer, writer: ResourceWriter, config: Config) -> None:
  # step 2: run kustomize
  apps = [app for app in viewer.get_dirs_children(depth=1)]
  for env in config.envs:
    for app in apps:
      env_child = app.get_child(env)
      if env_child:
        yml_child = env_child.get_child('kustomization.yml')
        if yml_child:
          dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
          process = subprocess.Popen(['kubectl', 'kustomize',
                                      os.path.join(viewer.root_element_abs_path, dir_rel_path)],
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      universal_newlines=True)
          stdout, stderr = process.communicate()

          for resource_kind, resource_name, resource_yml in multi_resource_parser(stdout):
            writer.update_resource(os.path.join(env, app.name), resource_kind, resource_name, resource_yml)
          log.debug(stdout)
      else:
        yml_child = app.get_child('kustomization.yml')
        if yml_child:
          dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
          process = subprocess.Popen(['kubectl', 'kustomize',
                                      os.path.join(viewer.root_element_abs_path, dir_rel_path)],
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      universal_newlines=True)
          stdout, _ = process.communicate()

          for resource_kind, resource_name, resource_yml in multi_resource_parser(stdout):
            writer.update_resource(os.path.join(env, app.name), resource_kind, resource_name, resource_yml)
          log.debug(stdout)
        else:
          yml_children = app.get_files_children('.yml$')

          for yml_child in yml_children:
            dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
            for resource_kind, resource_name, resource_yml in multi_resource_parser(yml_child.content):
              writer.update_resource(os.path.join(env, app.name), resource_kind, resource_name, resource_yml)

def main() -> None:
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--env', type=str, default=None, help='Environment to render')
  parser.add_argument('--app', type=str, default=None, help='Application to render')
  parser.add_argument('--root-dir', type=str, default=os.getcwd(), help='Root directory')
  parser.add_argument('--config-file', type=str, default=CONFIG_FILE, help='Configuration file')
  args = parser.parse_args()

  root_dir = args.root_dir
  log.debug('Root directory path: {}'.format(root_dir))

  config = read_config(root_dir, args.config_file)
  if os.path.exists(config.config['tmp_dir']):
    shutil.rmtree(config.config['tmp_dir'])

  source_viewer = build_resource_viewer(config.config['source_dir'], args.app)
  tmp_writer = build_resource_writer(config.config['tmp_dir'], config.envs, args.env)
  step_1(source_viewer, tmp_writer, config)
  tmp_writer.write_updates()

  tmp_viewer = build_resource_viewer(config.config['tmp_dir'], args.app)
  output_writer = build_resource_writer(config.config['output_dir'], config.envs, args.env)
  step_2(tmp_viewer, output_writer, config)
  #TODO: clean only filtered apps/envs
  if os.path.exists(config.config['output_dir']):
    shutil.rmtree(config.config['output_dir'])
  output_writer.write_updates()
