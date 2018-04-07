import abc
import jinja2
import math
import pathlib
import shutil
import typing

import config
import plugin
import template


def is_renderable(file_: typing.IO) -> bool:
    """
    >>> import io

    >>> f = io.StringIO('---\\ntitle: hello\\n---\\ncontent\\n')
    >>> is_renderable(f)
    True

    >>> f = io.StringIO('content\\n')
    >>> is_renderable(f)
    False
    """

    try:
        return file_.read(4) == '---\n'
    except:
        return False


def read_renderable_file(file_: typing.IO) -> typing.Tuple[config.Config, str]:
    """
    >>> import io

    >>> f = io.StringIO('---\\ntitle: hello\\n---\\ncontent\\n')
    >>> config, content = read_renderable_file(f)
    >>> config.as_dict()
    {'title': 'hello'}
    >>> content
    'content\\n'
    """

    headers: typing.List[str] = []
    contents: typing.List[str] = []

    target = headers
    for i, line in enumerate(file_):
        if i == 0:
            continue

        if line == '---\n' and target is not contents:
            target = contents
            continue
        target.append(line)

    return config.Config(''.join(headers)), ''.join(contents)


class FileTreeNode:
    def __init__(self, parent: 'Directory' = None) -> None:
        self.parent = parent


class Directory(FileTreeNode, typing.Iterable[FileTreeNode]):
    def __init__(self,
                 source: pathlib.Path,
                 parent: 'Directory' = None,
                 plugins: plugin.Plugins = None) -> None:

        super().__init__(parent)

        self.source = source
        if plugins is None:
            self.plugins = plugin.Plugins()
        else:
            self.plugins = plugins

        self.template: template.TemplateManager = template.TemplateManager(
            self.source,
            parent.template if parent is not None else None,
        )

        self.config: config.Config = config.Config.from_path(
            source,
            parent.config if parent is not None else None,
        )

    def __str__(self) -> str:
        root = self.root_path()

        if root == self.source:
            return '<Directory />'
        else:
            path = self.source.relative_to(root).as_posix()

            return '<Directory /{}>'.format(path)

    def root_path(self) -> pathlib.Path:
        if self.parent is not None:
            return self.parent.root_path()
        else:
            return self.source

    def get_converter(self, suffix) -> plugin.ConverterType:
        return self.plugins.get_converter(suffix)

    def _user_index_page(self) -> typing.Optional['Page']:
        for candidate in sorted(self.source.glob('index.*')):
            if candidate.suffix == '.html' or is_renderable(candidate.open()):
                return Page(candidate, self)

        return None

    def auto_index_pages(self) -> typing.Iterator['AutoIndexPage']:
        if not self.config['autoindex'] or self._user_index_page() is not None:
            return

        confs = self.config['autoindex']
        if isinstance(confs, str):
            confs = [{'layout': confs}]

        if isinstance(confs, dict):
            confs = [confs]

        if isinstance(confs, list):
            for conf in confs:
                if isinstance(conf, str):
                    conf = {'layout': conf}

                children = tuple(self.get_children(conf.get('source', '*')))

                pagenate = conf.get('pagenate', 1)
                if not isinstance(pagenate, int) or pagenate <= 0:
                    pagenate = 1

                for i in range(0, len(children), pagenate):
                    yield AutoIndexPage(
                        children[i:i+pagenate],
                        self,
                        i // pagenate,
                        math.ceil(len(children) / pagenate),
                        conf.get('target', 'index.html'),
                        conf.get('layout', 'index.html'),
                    )

    def index_page(self) -> typing.Optional['Page']:
        user_index = self._user_index_page()
        if user_index is not None:
            return user_index

        if self.config['autoindex']:
            try:
                return next(self.auto_index_pages())
            except StopIteration:
                print('stop', self.source)
                pass

        return None

    def __iter__(self) -> typing.Iterator[FileTreeNode]:
        yield from self.auto_index_pages()

        for p in self.source.iterdir():
            if p.name.startswith('.'):
                continue

            if p.is_file():
                yield Page(p, self)
            else:
                yield Directory(p, self, self.plugins)

    def pages(self) -> typing.Iterator['Page']:
        for page in self:
            if isinstance(page, Page):
                if not isinstance(page, IndexPageMixIn):
                    yield page
            elif isinstance(page, Directory):
                index = page.index_page()
                if index is not None:
                    yield index

    def walk(self) -> typing.Iterator[FileTreeNode]:
        for p in self:
            if isinstance(p, Directory):
                yield p
                yield from p.walk()
            else:
                yield p

    def get_child(self, path: pathlib.Path) -> FileTreeNode:
        dir_ = self
        for i, p in enumerate(reversed(path.relative_to(self.source).parents)):
            if i != 0:
                dir_ = Directory(self.source / p, dir_, self.plugins)

        if path.is_file():
            return Page(path, dir_)
        else:
            return Directory(path, dir_, self.plugins)

    def get_children(self, pattern: str) -> typing.Iterator[FileTreeNode]:
        def is_hidden(path):
            for p in path.relative_to(self.source).parents:
                if p.name.startswith('.'):
                    return True
            return path.name.startswith('.')

        for path in self.source.glob(pattern):
            if not is_hidden(path) and path.stem != 'index':
                yield self.get_child(path)


class Page(FileTreeNode, metaclass=abc.ABCMeta):
    def __init__(self, parent: Directory) -> None:
        super().__init__(parent)

    def __new__(cls: typing.Type,
                source: pathlib.Path,
                parent: Directory) -> 'Page':

        if cls is Page:
            if is_renderable(source.open()):
                if source.stem == 'index':
                    cls = IndexPage
                else:
                    cls = ArticlePage
            else:
                cls = AssetPage

        self = FileTreeNode.__new__(cls)
        self.__init__(source, parent)
        return self

    def __str__(self) -> str:
        return '<{} {}>'.format(self.__class__.__name__, '/' / self.path())

    @abc.abstractmethod
    def path(self) -> pathlib.Path:
        pass

    def url(self) -> str:
        return ('/' / self.path()).as_posix()

    @abc.abstractmethod
    def render(self, out: typing.BinaryIO) -> None:
        pass

    @abc.abstractmethod
    def page_info(self) -> config.Config:
        pass

    def parent_page(self) -> typing.Optional['Page']:
        return self.parent.index_page()

    def children(self) -> typing.Iterator['Page']:
        return iter([])

    def brothers(self) -> typing.Iterator['Page']:
        for page in self.parent.pages():
            if page.url() != self.url():
                yield page

    def relations_info(self,
                       ignore_urls: typing.Set[str] = set()) -> typing.Mapping:
        ignore_urls = set(ignore_urls)
        ignore_urls.add(self.url())

        parent_page = self.parent_page()
        parent_info = parent_page.page_info() if parent_page else None

        return {
            'children': [
                p.page_info().overlay(p.relations_info(ignore_urls)).as_dict()
                for p in self.children() if p.url() not in ignore_urls
            ],
            'brothers': [
                p.page_info().overlay(p.relations_info(ignore_urls)).as_dict()
                for p in self.brothers() if p.url() not in ignore_urls
            ],
            'parent': parent_info.as_dict() if parent_info else None,
        }


class AssetPage(Page):
    def __init__(self, source: pathlib.Path, parent: Directory) -> None:
        super().__init__(parent)

        self._source = source
        self._path = source.relative_to(parent.root_path())

    def path(self) -> pathlib.Path:
        return self._path

    def render(self, out: typing.BinaryIO) -> None:
        shutil.copyfileobj(self._source.open('rb'), out)

    def page_info(self) -> config.Config:
        return config.Config({
            'path': pathlib.PurePosixPath('/' / self.path()),
            'url': self.url(),
        })


class RenderablePage(Page, metaclass=abc.ABCMeta):
    def __init__(self,
                 path: pathlib.Path,
                 parent: Directory,
                 config: config.Config,
                 content: str = '') -> None:

        super().__init__(parent)

        self._path = path

        self.config = config
        self.content = content

    def path(self) -> pathlib.Path:
        return self._path

    def page_info(self) -> config.Config:
        return self.config.overlay({
            'path': pathlib.PurePosixPath('/' / self.path()),
            'url': self.url(),
        })

    def rendering_context(self) -> config.Config:
        return (self.parent.config.overlay(self.relations_info())
                                  .overlay({'page': self.page_info()}))

    def rendering_context_with_content(self) -> config.Config:
        context = self.rendering_context()

        converter = self.parent.get_converter(self.suffix())
        content = converter(self.content, context.as_dict())

        return context.overlay({'content': content})

    def suffix(self) -> typing.Optional[str]:
        return None

    @abc.abstractmethod
    def layout(self) -> str:
        pass

    def render(self, out: typing.BinaryIO) -> None:
        out.write(self.parent.template.render(
            self.layout(),
            self.rendering_context_with_content(),
        ).encode('utf-8'))


class ArticlePage(RenderablePage):
    def __init__(self, source: pathlib.Path, parent: Directory) -> None:
        basepath = source.relative_to(parent.root_path()).parent
        path = basepath / (source.stem + '.html')

        super().__init__(path, parent, *read_renderable_file(source.open()))

        self.source = source

    def suffix(self) -> typing.Optional[str]:
        return self.source.suffix

    def layout(self) -> str:
        page = self.config['page']

        if isinstance(page, dict) and 'layout' in page:
            return page['layout'] or 'default.html'

        return 'default.html'


class IndexPageMixIn(Page):
    def parent_page(self) -> typing.Optional['Page']:
        if self.parent.parent is not None:
            return self.parent.parent.index_page()
        else:
            return None

    def children(self) -> typing.Iterator['Page']:
        for page in self.parent.pages():
            yield page

    def brothers(self) -> typing.Iterator['Page']:
        if self.parent.parent is None:
            return

        for page in self.parent.parent.pages():
            if page.url() != self.url():
                yield page

    def url(self) -> str:
        directory_slash = self.config['directory_slash']
        if directory_slash is None:
            directory_slash = self.parent.config['directory_slash']

        if directory_slash == 'index.html':
            return '/' + self.path().as_posix()

        path = ('/' / self.path().parent).as_posix()

        if directory_slash is not False and path != '/':
            path += '/'

        return path


class IndexPage(ArticlePage, IndexPageMixIn):
    pass


class AutoIndexPage(RenderablePage, IndexPageMixIn):
    def __init__(self,
                 sources: typing.Iterable[FileTreeNode],
                 parent: Directory,
                 page_num: int = 0,
                 page_max: int = 1,
                 file_name: str = 'index.html',
                 layout: str = 'index.html') -> None:

        fname = jinja2.Template(file_name).render({'pagenate': {
            'num': page_num,
            'max': page_max,
        }})
        path = parent.source.relative_to(parent.root_path()) / fname

        page_config = parent.config['page']

        conf = config.Config(page_config
                             if isinstance(page_config, dict)
                             else {})
        super().__init__(path, parent, conf)

        self.page_num = page_num
        self.page_max = page_max

        self.sources = tuple(sources)
        self._layout = layout

    def contents(self) -> typing.Iterator[typing.Mapping[str, typing.Any]]:
        for p in self.sources:
            if isinstance(p, Page):
                yield p.rendering_context_with_content()
            elif isinstance(p, Directory):
                index = p.index_page()
                if index is not None:
                    yield index.rendering_context_with_content()

    def __new__(cls: typing.Type, *args, **kwds) -> None:
        self = FileTreeNode.__new__(cls)
        self.__init__(*args, **kwds)
        return self

    def rendering_context(self) -> config.Config:
        return super().rendering_context().overlay({
            'pagenate': {'num': self.page_num, 'max': self.page_max},
        })

    def rendering_context_with_content(self) -> config.Config:
        return self.rendering_context().overlay({
            'content': tuple(self.contents()),
        })

    def layout(self) -> str:
        return self._layout
