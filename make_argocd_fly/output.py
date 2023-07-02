import logging
import os

log = logging.getLogger(__name__)


class OutputRenderer:
  def __init__(self, output_dir: str, envs: list) -> None:
    self.output_dir = output_dir
    self.envs = envs

  def write_file(self, relative_dir: str, filename: str, content: str) -> None:
    path = os.path.join(self.output_dir, relative_dir)
    os.makedirs(path, exist_ok=True)

    with open(os.path.join(path, filename), 'w') as f:
      f.write(content)
