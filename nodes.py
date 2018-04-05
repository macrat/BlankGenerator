import abc
import pathlib
import shutil
import typing

import config
import plugin
import template


def is_renderable(file_: typing.IO) -> bool:
    try:
        return file_.read(4) == '---\n'
    except:
        return False


def read_renderable_file(file_: typing.IO) -> typing.Tuple[config.Config, str]:
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
            return iter([])

        return iter([AutoIndexPage(self)])

    def index_page(self) -> typing.Optional['Page']:
        user_index = self._user_index_page()
        if user_index is not None:
            return user_index

        if self.config['autoindex']:
            return next(self.auto_index_pages())

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

    def suffix(self) -> typing.Optional[str]:
        return None

    @abc.abstractmethod
    def layout(self) -> str:
        pass

    def render(self, out: typing.BinaryIO) -> None:
        context = self.rendering_context()

        converter = self.parent.get_converter(self.suffix())
        content = converter(self.content, context.as_dict())

        out.write(self.parent.template.render(self.layout(), context.overlay({
            'content': content,
        })).encode('utf-8'))


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
    def __init__(self, parent: Directory) -> None:
        path = parent.source.relative_to(parent.root_path()) / 'index.html'

        page_config = parent.config['page']

        conf = config.Config(page_config
                             if isinstance(page_config, dict)
                             else {})
        super().__init__(path, parent, conf)

    def __new__(cls: typing.Type, parent: Directory) -> None:
        self = FileTreeNode.__new__(cls)
        self.__init__(parent)
        return self

    def layout(self) -> str:
        return str(self.parent.config['autoindex'] or 'index.html')
