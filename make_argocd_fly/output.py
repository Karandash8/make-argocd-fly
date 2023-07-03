import logging
import os
import re

log = logging.getLogger(__name__)


class OutputRenderer:
  def __init__(self, output_dir: str, envs: list) -> None:
    self.output_dir = output_dir
    self.envs = envs

  def write_file(self, relative_dir: str, filename: str, resource: str) -> None:
    path = os.path.join(self.output_dir, relative_dir)
    os.makedirs(path, exist_ok=True)

    if not os.path.exists(os.path.join(path, filename)):
      with open(os.path.join(path, filename), 'w') as f:
        f.write(resource)
    else:
      with open(os.path.join(path, filename), 'r') as f:
        file_content = f.read()

      if not re.search(resource, file_content):
        with open(os.path.join(path, filename), 'a') as f:
          f.write('---')
          f.write(resource)
