import logging
import os

log = logging.getLogger(__name__)

SOURCE_DIR = 'source'
OUTPUT_DIR = 'output'
TMP_DIR = '.tmp'


class Config:
  def __init__(self, root_dir: str, config: dict) -> None:
    self.root_dir = root_dir

    try:
      self.config = config['config']
      self.envs = config['envs']
      self.vars = config['vars']
    except KeyError as error:
      log.error('Missing configuration')
      log.fatal(error)
      raise

    if 'source_dir' not in self.config:
      self.config['source_dir'] = SOURCE_DIR
    self.config['source_dir'] = os.path.join(self.root_dir, self.config['source_dir'])

    if 'output_dir' not in self.config:
      self.config['output_dir'] = OUTPUT_DIR
    self.config['output_dir'] = os.path.join(self.root_dir, self.config['output_dir'])

    if 'tmp_dir' not in self.config:
      self.config['tmp_dir'] = TMP_DIR
    self.config['tmp_dir'] = os.path.join(self.root_dir, self.config['tmp_dir'])
