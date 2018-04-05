import argparse
import pathlib

import utils
import watch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Static site generator.')

    parser.add_argument('source',
                        metavar='SOURCE',
                        default='./',
                        nargs='?',
                        help='The directory of source files. (default: ./)')

    parser.add_argument('-o',
                        '--output',
                        metavar='DIRECTORY',
                        default='./_site',
                        help='The directory for output. (default: ./_site)')

    parser.add_argument(
        '-w',
        '--watch',
        action='store_true',
        help='Enable watching source directory and auto rebuild.',
    )

    args = parser.parse_args()

    src = pathlib.Path(args.source)
    dest = pathlib.Path(args.output)

    if args.watch:
        watch.run(src, dest)
    else:
        utils.build_all(src, dest)
