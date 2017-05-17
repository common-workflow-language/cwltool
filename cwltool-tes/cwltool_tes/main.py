import os
import sys
import argparse
import logging
import yaml

import cwltool.main

from tes import TESPipeline

log = logging.getLogger('tes-backend')
log.setLevel(logging.DEBUG)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
log.addHandler(console)


def main(args):
    parser = cwltool.main.arg_parser()
    parser = add_args(parser)
    parsed_args = parser.parse_args(args)
    if not len(args) >= 1:
        parser.print_help()
        return 1

    if parsed_args.tes is not None:
        pipeline = TESPipeline(parsed_args.tes, vars(parsed_args))
        cwltool.main.main(
            args=parsed_args,
            makeTool=pipeline.make_tool
        )
    else:
        cwltool.main.main(
            args=parsed_args
        )

def add_args(parser):
    parser.add_argument(
        "--tes",
        type=str,
        default="http://localhost:8000",
        help="GA4GH TES Service URL"
    )
    return parser


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
