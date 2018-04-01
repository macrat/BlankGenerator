import mimetypes
import typing


ConverterType = typing.Callable[[str], str]


class ConvertersMap(dict, typing.MutableMapping[str, ConverterType]):
    def default_converter(self, content: str) -> str:
        return content

    def __getitem__(self, mimetype: str) -> ConverterType:
        return self.get(mimetype, self.default_converter)


converters = ConvertersMap()


def converter(mimetype) -> typing.Callable[[ConverterType], ConverterType]:
    def __(fun: ConverterType) -> ConverterType:
        converters[mimetype] = fun
        return fun
    return __


def mimetype(mimetype: str, extension: str) -> None:
    mimetypes.add_type(mimetype, extension, False)


def guess_mimetype(path: str) -> str:
    return mimetypes.guess_type(path, False)[0]
