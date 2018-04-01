import pathlib
import importlib.machinery


plugins = []


for p in pathlib.Path('./plugins').iterdir():
    if p.is_file() and p.suffix == '.py' and p.name != '__init__.py':
        plugins.append(importlib.machinery.SourceFileLoader(
            'plugins::' + p.stem,
            str(p.resolve()),
        ).load_module())
