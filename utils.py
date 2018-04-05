import pathlib
import sys
import typing

import nodes


def build_all(src: pathlib.Path,
              dest: pathlib.Path,
              log: typing.TextIO = sys.stdout) -> None:

    dir_ = nodes.Directory(src)

    for page in dir_.walk():
        if isinstance(page, nodes.Page):
            out_path = dest / page.path()

            print('{} -> {} ({})'.format(page.path(), out_path, page.url()),
                  file=log)

            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open('wb') as fp:
                page.render(fp)
