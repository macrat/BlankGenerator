import abc
import collections
import mimetypes
import pathlib
import typing

import jinja2
import markdown
import yaml


class TemplateLoader(jinja2.BaseLoader):
    def __init__(self,
                 path: pathlib.Path,
                 parent: 'TemplateLoader' = None) -> None:

        self.path = path
        self.parent = parent

    def __str__(self) -> str:
        return '<TemplateLoader {}>'.format(self.path)

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

        return source, path.resolve(), lambda: path.stat().st_mtime == mtime


def merge_dict(x: dict, y: dict) -> dict:
    """ merging dictionary


    Merge two dictionaries. Override with a value of `y` if key was collision.
    >>> merge_dict({'a': 1, 'b': 2, 'c': 4}, {'c': 0, 'd': 10})
    {'a': 1, 'b': 2, 'c': 0, 'd': 10}

    Merge will do recursively.
    >>> merge_dict({'parent': {'child': 1}}, {'parent': {'children': [2, 3]}})
    {'parent': {'child': 1, 'children': [2, 3]}}
    """

    result = {}

    for k, v in x.items():
        result[k] = v

    for k, v in y.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = merge_dict(result[k], v)
        else:
            result[k] = v

    return result


class Config(collections.abc.Mapping):
    def __init__(self,
                 data: typing.Union[str, dict],
                 parent: 'Config' = None) -> None:

        self.parent = parent

        self._config = data if isinstance(data, dict) else yaml.load(data)
        if self._config is None:
            self._config = {}

        if parent is not None:
            self._config = merge_dict(dict(parent), self._config)

    @classmethod
    def from_path(cls,
                  path: pathlib.Path,
                  parent: 'Config' = None) -> 'Config':

        try:
            with (path / '.bg.yml').open() as f:
                return cls(f.read(), parent)
        except FileNotFoundError:
            return cls('', parent)

    def __getitem__(self, key: str) -> object:
        return self._config.get(key)

    def __iter__(self) -> typing.Iterator:
        return iter(self._config)

    def __len__(self) -> int:
        return len(self._config)

    def __dict__(self, key: str) -> dict:
        return dict(self._config)

    def __str__(self):
        return str(self._config)

    def overlay(self, another: dict) -> 'Config':
        return Config(merge_dict(self._config, another), self)


class Page:
    def __init__(self,
                 path: pathlib.Path,
                 parent: 'Directory') -> None:

        self.path = path
        self.parent: typing.Optional['Directory'] = parent

        self.renderable = False
        try:
            with self.path.open() as f:
                self.renderable = f.read(4) == '---\n'
        except:
            pass

        if self.renderable:
            headers = []
            contents = []
            with path.open() as f:
                target = headers
                for i, line in enumerate(f):
                    if i == 0:
                        continue

                    if line == '---\n' and target is not contents:
                        target = contents
                        continue
                    target.append(line)
            header = ''.join(headers)
            self.content = ''.join(contents)
        else:
            header = ''
            with path.open('rb') as f:
                self.content = f.read()

        self.config = parent.config.overlay({'page': dict(Config(header))})
        self.config = self.config.overlay({'page': {
            'path': self.output_path,
            'url': self.url,
        }})

    def __str__(self) -> str:
        return '<Page {}>'.format(self.path)

    @property
    def type(self) -> typing.Optional[str]:
        mimetypes.add_type('text/markdown', '.md', False)
        mimetypes.add_type('text/markdown', '.markdown', True)
        return mimetypes.guess_type(self.path.name, False)[0]

    @property
    def layout(self) -> str:
        if 'layout' in self.config['page']:
            return self.config['page']['layout'] or 'default.html'
        return 'default.html'

    @property
    def template(self) -> jinja2.Template:
        if self.is_dir:
            return self.template_environment.get_template(self.layout)
        else:
            return self.parent.template_environment.get_template(self.layout)

    @property
    def page_info(self) -> dict:
        return self.config['page'] or {}

    def relations_info(self, ignore_urls: typing.Set[str] = set()) -> dict:
        ignore_urls.add(self.url)

        base = self
        if not self.is_dir and self.output_path.name == 'index.html':
            base = self.parent

        if not base.is_dir:
            return {
                'children': [],
                'brothers': [],
                'parent': base.parent.page_info,
            }

        return {
            'children': [
                merge_dict(x.page_info, x.relations_info(set(ignore_urls)))
                for x in base.child_pages if x.url not in ignore_urls
            ],
            'brothers': [
                merge_dict(x.page_info, x.relations_info(set(ignore_urls)))
                for x in base.parent.child_pages if x.url not in ignore_urls
            ] if base.parent is not None else [],
            'parent': None if base.parent is None else base.parent.page_info,
        }

    def render(self, content: str) -> str:
        return self.template.render(
            **self.config.overlay(self.relations_info())
                         .overlay({'content': content}),
        )

    @property
    def is_page(self) -> bool:
        return True

    @property
    def is_dir(self) -> bool:
        return False

    @property
    def root_path(self) -> pathlib.Path:
        if self.parent is None:
            return self.path
        else:
            return self.parent.root_path

    @property
    def relative_path(self) -> pathlib.Path:
        return self.path.relative_to(self.root_path)

    @property
    def output_path(self) -> pathlib.Path:
        return self.relative_path.parent / (self.path.stem + '.html')

    @property
    def url(self, directory_type: str = 'slash') -> pathlib.Path:
        dir_ = pathlib.PurePosixPath(
            '/' + self.relative_path.parent.as_posix(),
        )

        name = self.relative_path.stem + '.html'

        if name == 'index.html':
            if self.config['directory_slash'] == 'index.html':
                return (dir_ / 'index.html').as_posix()
            elif self.config['directory_slash'] is False:
                return dir_.as_posix()
            elif dir_.as_posix() == '/':
                return '/'
            else:
                return dir_.as_posix() + '/'
        else:
            return (dir_ / name).as_posix()


class Directory(Page):
    def __init__(self, path: pathlib.Path, parent: 'Directory' = None) -> None:
        self.path = path
        self.parent = parent

        self.config = Config.from_path(
            path,
            parent.config if parent is not None else None,
        )
        self.config = self.config.overlay({'page': {
            'path': self.output_path,
            'url': self.url,
        }})

        self.content = ''

        self.template_environment = jinja2.Environment(loader=TemplateLoader(
            self.path,
            parent.template_environment.loader if parent is not None else None,
        ))

        self.renderable = self.is_page

    def __str__(self) -> str:
        return '<Directory {}>'.format(self.path)

    def __iter__(self) -> typing.Iterable[Page]:
        for p in self.path.iterdir():
            if p.name.startswith('.'):
                continue

            if p.is_file():
                yield Page(p, self)
            else:
                yield Directory(p, self)

    def walk(self) -> typing.Iterable[Page]:
        for p in self:
            if p.is_dir:
                yield p
                yield from p.walk()
            else:
                yield p

    @property
    def child_pages(self) -> typing.Iterable[Page]:
        for p in self:
            if not p.is_dir:
                yield p
            else:
                index = p.index_page
                if index is not None:
                    yield index

    @property
    def index_page(self) -> typing.Optional[Page]:
        candidates = sorted(self.path.glob('index.*'))

        if len(candidates) > 0:
            return Page(candidates[0], self)

        if self.config['autoindex']:
            return self
        else:
            None

    @property
    def auto_index_enabled(self) -> bool:
        return self.config['autoindex'] and self.index_page is not None

    @property
    def type(self) -> typing.Optional[str]:
        return None

    @property
    def layout(self):
        return self.config['autoindex'] or 'index.html'

    @property
    def is_page(self) -> bool:
        return self.auto_index_enabled

    @property
    def is_dir(self) -> bool:
        return True

    @property
    def relative_path(self) -> pathlib.Path:
        return self.path.relative_to(self.root_path) / 'index.html'

    @property
    def output_path(self) -> pathlib.Path:
        return self.relative_path


if __name__ == '__main__':
    dir_ = Directory(pathlib.Path('./src'))

    for f in dir_.walk():
        out_path = pathlib.Path('./dist') / f.output_path

        print(f.path, '->', out_path, '({})'.format(f.url))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if f.renderable:
            if f.type == 'text/markdown':
                content = markdown.Markdown().convert(f.content)
            else:
                content = f.content

            with out_path.open('w') as fp:
                fp.write(f.render(content))
        else:
            with out_path.open('wb') as fp:
                fp.write(f.content)
