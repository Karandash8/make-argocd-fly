import logging
import logging.config
import yaml
import os
import argparse
import subprocess
import shutil
import re
from jinja2 import Environment, FileSystemLoader

from make_argocd_fly.init import read_config, build_source_viewer, build_output_renderer

LOG_CONFIG_FILE = 'log_config.yml'
TMP_DIR = '.tmp'
CONFIG_FILE = 'config.yml'
SOURCE_DIR = 'source'
OUTPUT_DIR = 'output'

try:
  with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), LOG_CONFIG_FILE)) as f:
    yaml_config = yaml.safe_load(f.read())
    logging.config.dictConfig(yaml_config)
except FileNotFoundError:
  logging.basicConfig(level='DEBUG')

log = logging.getLogger(__name__)


def kustomize_parser(input: str) -> tuple[str, str]:
  log.debug(input)

  resources = []
  for resource in input.split('---'):
    resource_name = re.search('\nkind:(.*)', resource).group(1).strip()
    resources.append((resource_name, resource))

  return resources

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Render ArgoCD Applications.')
  parser.add_argument('--env', type=str, default=None, help='Environment to render')
  parser.add_argument('--app', type=str, default=None, help='Application to render')
  parser.add_argument('--root-path', type=str, default=os.path.dirname(os.path.realpath(__file__)), help='Root directory')
  args = parser.parse_args()

  root_path = args.root_path
  log.debug('Root directory path: {}'.format(root_path))

  config = read_config(os.path.join(root_path, CONFIG_FILE))
  source_viewer = build_source_viewer(root_path, SOURCE_DIR, args.app)
  tmp_output_renderer = build_output_renderer(os.path.join(root_path, TMP_DIR), config['envs'], args.env)

  if os.path.exists(os.path.join(root_path, TMP_DIR)):
    shutil.rmtree(os.path.join(root_path, TMP_DIR))

  # step 1: copy .yml files, render .j2 files
  environment = Environment(loader=FileSystemLoader(source_viewer.source_dir))
  apps = [app for app in source_viewer.list_dirs_children(depth=1)]
  for app in apps:
    yml_children = source_viewer.get_child(app.name).list_files_children('.yml$')
    j2_children = source_viewer.get_child(app.name).list_files_children('.j2$')
    log.debug('app: {}, yml files: {}, j2_files: {}'.format(app.name, [child.relative_path for child in yml_children], [child.relative_path for child in j2_children]))

    for yml_child in yml_children:
      relative_dir = '/'.join(yml_child.relative_path.split('/')[:-1])
      tmp_output_renderer.write_file(relative_dir, yml_child.name, ''.join(yml_child.content))

    for j2_child in j2_children:
      relative_dir = '/'.join(j2_child.relative_path.split('/')[:-1])
      template = environment.get_template(j2_child.relative_path)
      tmp_output_renderer.write_file(relative_dir, j2_child.name[:-3], template.render(config['vars']))

  tmp_source_viewer = build_source_viewer(root_path, TMP_DIR, args.app)
  output_renderer = build_output_renderer(os.path.join(root_path, OUTPUT_DIR), config['envs'], args.env)

  # step 2: run kustomize
  apps = [app for app in tmp_source_viewer.list_dirs_children(depth=1)]
  for env in config['envs']:
    for app in apps:
      env_child = app.get_child(env)
      if env_child:
        yml_child = env_child.get_child('kustomization.yml')
        if yml_child:
          relative_dir = '/'.join(yml_child.relative_path.split('/')[:-1])
          process = subprocess.Popen(['kubectl', 'kustomize',
                                      os.path.join(tmp_source_viewer.source_dir, relative_dir)],
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                      universal_newlines=True)
          stdout, stderr = process.communicate()

          resources = kustomize_parser(stdout)
          for resource_name, resource in resources:
            output_renderer.write_file(os.path.join(output_renderer.output_dir, env, app.name), resource_name + '.yml', resource)
          log.debug(stdout)
      else:
        base_child= app.get_child('base')
        if base_child:
          yml_child = base_child.get_child('kustomization.yml')
          if yml_child:
            relative_dir = '/'.join(yml_child.relative_path.split('/')[:-1])
            process = subprocess.Popen(['kubectl', 'kustomize',
                                        os.path.join(tmp_source_viewer.source_dir, relative_dir)],
                                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                        universal_newlines=True)
            stdout, stderr = process.communicate()

            resources = kustomize_parser(stdout)
            for resource_name, resource in resources:
              output_renderer.write_file(os.path.join(output_renderer.output_dir, env, app.name), resource_name + '.yml', resource)
            log.debug(stdout)
        else:
          yml_children = app.list_files_children('.yml$')

          for yml_child in yml_children:
            relative_dir = '/'.join(yml_child.relative_path.split('/')[:-1])
            output_renderer.write_file(os.path.join(output_renderer.output_dir, env, app.name), yml_child.name, ''.join(yml_child.content))
