import warnings
import atexit
import logging


log = logging.getLogger(__name__)

warnings.simplefilter('default')

collected_warnings = []


def deferred_showwarning(message, category, filename, lineno, file=None, line=None):
  collected_warnings.append(warnings.formatwarning(message, category, filename, lineno, line))


@atexit.register
def print_warnings():
  if collected_warnings:
    for warning in collected_warnings:
      log.warning(warning)


def init_warnings():
  warnings.showwarning = deferred_showwarning
