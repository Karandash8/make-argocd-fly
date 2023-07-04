import logging
import logging.config
import yaml
import os
import argparse
import subprocess
import shutil
from jinja2 import Environment, FileSystemLoader

from make_argocd_fly.init import read_config, build_resource_viewer, build_resource_writer
from make_argocd_fly.utils import extract_dir_rel_path, multi_resource_parser, resource_parser

LOG_CONFIG_FILE = 'log_config.yml'
CONFIG_FILE = 'config.yml'


def configure_logging(log_config_file: str) -> None:
  try:
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), log_config_file)) as f:
      yaml_config = yaml.safe_load(f.read())
      logging.config.dictConfig(yaml_config)
  except FileNotFoundError:
    logging.basicConfig(level='DEBUG')

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--env', type=str, default=None, help='Environment to render')
  parser.add_argument('--app', type=str, default=None, help='Application to render')
  parser.add_argument('--root-dir', type=str, default=os.getcwd(), help='Root directory')
  parser.add_argument('--log-config-file', type=str, default=LOG_CONFIG_FILE, help='Logging configuration file')
  args = parser.parse_args()

  configure_logging(args.log_config_file)
  log = logging.getLogger(__name__)

  root_dir = args.root_dir
  log.debug('Root directory path: {}'.format(root_dir))

  config = read_config(root_dir, CONFIG_FILE)
  if os.path.exists(config.config['tmp_dir']):
    shutil.rmtree(config.config['tmp_dir'])

  source_viewer = build_resource_viewer(config.config['source_dir'], args.app)
  tmp_writer = build_resource_writer(config.config['tmp_dir'], config.envs, args.env)

  # step 1: copy .yml files, render .j2 files
  environment = Environment(loader=FileSystemLoader(source_viewer.root_element_abs_path))
  apps = [app for app in source_viewer.get_dirs_children(depth=1)]
  for app in apps:
    yml_children = source_viewer.get_child(app.name).get_files_children('.yml$')
    j2_children = source_viewer.get_child(app.name).get_files_children('.j2$')
    log.debug('app: {}, yml files: {}, j2_files: {}'.format(app.name, [child.element_rel_path for child in yml_children], [child.element_rel_path for child in j2_children]))

    for yml_child in yml_children:
      dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
      tmp_writer.write_file(dir_rel_path, yml_child.name, yml_child.content)

    for j2_child in j2_children:
      dir_rel_path = extract_dir_rel_path(j2_child.element_rel_path)
      template = environment.get_template(j2_child.element_rel_path)
      tmp_writer.write_file(dir_rel_path, j2_child.name[:-3], template.render(config.vars))

  tmp_viewer = build_resource_viewer(config.config['tmp_dir'], args.app)
  output_writer = build_resource_writer(config.config['output_dir'], config.envs, args.env)

  # step 2: run kustomize
  apps = [app for app in tmp_viewer.get_dirs_children(depth=1)]
  for env in config.envs:
    for app in apps:
      env_child = app.get_child(env)
      if env_child:
        yml_child = env_child.get_child('kustomization.yml')
        if yml_child:
          dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
          process = subprocess.Popen(['kubectl', 'kustomize',
                                      os.path.join(tmp_viewer.root_element_abs_path, dir_rel_path)],
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      universal_newlines=True)
          stdout, stderr = process.communicate()

          for resource_kind, _, resource_yml in multi_resource_parser(stdout):
            output_writer.update_resource(os.path.join(env, app.name), resource_yml)
          log.debug(stdout)
      else:
        base_child= app.get_child('base')
        if base_child:
          yml_child = base_child.get_child('kustomization.yml')
          if yml_child:
            dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
            process = subprocess.Popen(['kubectl', 'kustomize',
                                        os.path.join(tmp_viewer.root_element_abs_path, dir_rel_path)],
                                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                        universal_newlines=True)
            stdout, stderr = process.communicate()

            for resource_kind, _, resource_yml in multi_resource_parser(stdout):
              output_writer.update_resource(os.path.join(env, app.name), resource_yml)
            log.debug(stdout)
        else:
          yml_children = app.get_files_children('.yml$')

          for yml_child in yml_children:
            dir_rel_path = extract_dir_rel_path(yml_child.element_rel_path)
            resource_kind, _ = resource_parser(yml_child.content)
            output_writer.write_file(os.path.join(env, app.name), resource_kind + '.yml', yml_child.content)
  output_writer.write_updates()
