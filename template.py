import pathlib
import typing

import jinja2


class Resolver(jinja2.BaseLoader):
    def __init__(self,
                 path: pathlib.Path,
                 parent: jinja2.BaseLoader = None) -> None:

        self.path = path
        self.parent = parent

    def __str__(self) -> str:
        return '<template.Resolver {}>'.format(self.path)

    def get_source(self, environment: jinja2.Environment, template: str) \
            -> typing.Tuple[str, str, typing.Callable[[], bool]]:

        path = self.path / '.template' / template

        if not path.exists():
            if self.parent is not None:
                return self.parent.get_source(environment, template)
            else:
                raise jinja2.TemplateNotFound(template)

        with path.open() as f:
            source = f.read()

        mtime = path.stat().st_mtime

        return (source,
                str(path.resolve()),
                lambda: path.stat().st_mtime == mtime)


class TemplateManager(jinja2.Environment):
    def __init__(self,
                 source_dir: pathlib.Path,
                 parent: jinja2.Environment = None) -> None:

        super().__init__(loader=Resolver(
            source_dir,
            parent.loader if parent is not None else None,
        ))
        self.source_dir = source_dir

    def __str__(self) -> str:
        return '<template.TemplateManager {}>'.format(self.source_dir)

    def render(self, name: str, context: typing.Mapping) -> str:
        return self.get_template(name).render(context)
