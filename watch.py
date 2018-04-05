import datetime
import pathlib
import sys

import utils


try:
    import pyinotify


    class Watcher(pyinotify.ProcessEvent):
        def __init__(self, src: pathlib.Path, dest: pathlib.Path) -> None:
            self.src = src
            self.dest = dest

            self.wm = pyinotify.WatchManager()
            self.notifier = pyinotify.Notifier(self.wm, self)
            self.wdd = self.wm.add_watch(str(src.resolve()), pyinotify.IN_CREATE | pyinotify.IN_MODIFY | pyinotify.IN_MOVED_FROM, rec=True)

        def loop(self) -> None:
            self.notifier.loop()

        def process_default(self, event) -> None:
            if (event is not None
                and event.name.startswith('.')
                and event.name != '.bg.yml'):

                return

            print(datetime.datetime.now(),
                  event.pathname if event is not None else '')

            try:
                utils.build_all(self.src, self.dest)
            except Exception as e:
                print(e, file=sys.stderr)

            print()


    def run(src: pathlib.Path, dest: pathlib.Path) -> None:
        watcher = Watcher(src, dest)
        watcher.process_default(None)
        watcher.loop()

except ImportError:
    def run(src: pathlib.Path, dest: pathlib.Path) -> None:
        print('error: pyinotify is not installed.', file=sys.stderr)
