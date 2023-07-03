import logging
import os

log = logging.getLogger(__name__)


def extract_dir_rel_path(path: str) -> str:
  return os.path.normpath('/'.join(path.split('/')[:-1]))
