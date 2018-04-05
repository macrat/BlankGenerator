import pathlib
import typing

import yaml


def merge_dict(x: typing.Mapping, y: typing.Mapping) -> dict:
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


class Config(typing.Mapping):
    def __init__(self,
                 data: typing.Union[str, dict],
                 parent: 'Config' = None) -> None:

        self.parent = parent

        self._config = data if isinstance(data, dict) else yaml.load(data)
        if self._config is None:
            self._config = {}

        if parent is not None:
            self._config = merge_dict(parent.as_dict(), self._config)

    @classmethod
    def from_path(cls,
                  path: pathlib.Path,
                  parent: 'Config' = None) -> 'Config':

        try:
            with (path / '.bg.yml').open() as f:
                return cls(f.read(), parent)
        except FileNotFoundError:
            return cls('', parent)

    def __str__(self) -> str:
        return '<Config {}>'.format(self._config)

    def as_dict(self) -> dict:
        return dict(self._config)

    def __getitem__(self, key: str) -> object:
        return self._config.get(key)

    def __iter__(self) -> typing.Iterator:
        return iter(self._config)

    def __len__(self) -> int:
        return len(self._config)

    def overlay(self, another: typing.Mapping) -> 'Config':
        return Config(merge_dict(self._config, another), self)
