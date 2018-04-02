import importlib.util
import pathlib
import typing


ConverterType = typing.Callable[[str, typing.Mapping[str, typing.Any]], str]


class ConvertersMap(dict, typing.MutableMapping[str, ConverterType]):
    def default_converter(self,
                          content: str,
                          context: typing.Mapping[str, typing.Any]) -> str:

        return content

    def __setitem__(self, suffix: str, converter: ConverterType) -> None:
        super().__setitem__(suffix.lower(), converter)

    def __getitem__(self, suffix: typing.Optional[str]) -> ConverterType:
        if isinstance(suffix, str):
            return self.get(suffix.lower(), self.default_converter)
        else:
            return self.default_converter


class Plugins:
    def __init__(self, path: pathlib.Path = pathlib.Path('./plugins')) -> None:
        self.converters = ConvertersMap()

        for p in path.iterdir():
            if not p.is_file():
                continue

            spec = importlib.util.spec_from_file_location(p.stem,
                                                          str(p.resolve()))
            if spec is None:
                continue

            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            # ignore errors because this is meta programming
            mod.init(Register(self))  # type: ignore

    def get_converter(self, suffix: str) -> ConverterType:
        return self.converters[suffix]


class Register:
    def __init__(self, plugins: Plugins) -> None:
        self._plugins = plugins

    def converter(self, suffix: str, converter: ConverterType) -> None:
        self._plugins.converters[suffix] = converter
