import argparse
import pathlib

import utils


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

    args = parser.parse_args()

    utils.build_all(pathlib.Path(args.source), pathlib.Path(args.output))
