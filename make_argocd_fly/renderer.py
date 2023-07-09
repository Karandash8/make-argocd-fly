import logging
from abc import ABC, abstractmethod
from jinja2 import Environment, BaseLoader, FileSystemLoader
from markupsafe import Markup

log = logging.getLogger(__name__)


class AbstractRenderer(ABC):
    def __init__(self, root_element_abs_path: str) -> None:
        super().__init__(root_element_abs_path)

    @abstractmethod
    def render(self, content: str, template_vars: dict = None) -> str:
        pass


class DummyRenderer:
    def __init__(self, root_element_abs_path: str) -> None:
        pass

    def render(self, content: str, template_vars: dict = None) -> str:
        return content


class JinjaRenderer:
    def __init__(self, root_element_abs_path: str = None) -> None:
        self.root_element_abs_path = root_element_abs_path
        if root_element_abs_path:
            self.loader = FileSystemLoader(root_element_abs_path)
        else:
            self.loader = BaseLoader()
        self.env = Environment(loader=self.loader)
        self.env.globals['include_file'] = self.include_file

    def include_file(self, path: str) -> None:
        return Markup(self.loader.get_source(self.env, path)[0])

    def render(self, content: str, template_vars: dict = None) -> str:
        template = self.env.from_string(content)

        return template.render(template_vars)
