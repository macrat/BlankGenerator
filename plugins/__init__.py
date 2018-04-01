import importlib.util
import pathlib


plugins = []


for p in pathlib.Path('./plugins').iterdir():
    if p.is_file() and p.suffix == '.py' and p.name != '__init__.py':
        spec = importlib.util.spec_from_file_location(p.stem, str(p.resolve()))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        plugins.append(mod)
