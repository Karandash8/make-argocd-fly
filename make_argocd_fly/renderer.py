import logging
from abc import ABC, abstractmethod
from jinja2 import Environment, BaseLoader

log = logging.getLogger(__name__)


class AbstractRenderer(ABC):
     @abstractmethod
     def render(self, content: str, template_vars: dict = None) -> str:
         pass


class DummyRenderer:
    def __init__(self) -> None:
        pass

    def render(self, content: str, template_vars: dict = None) -> str:
        return content


class JinjaRenderer:
    def __init__(self) -> None:
        pass

    def render(self, content: str, template_vars: dict = None) -> str:
        template = Environment(loader=BaseLoader).from_string(content)

        return template.render(template_vars)
