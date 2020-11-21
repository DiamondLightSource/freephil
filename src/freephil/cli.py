# Content in this file falls under the libtbx license

import optparse
import sys

import freephil


def main():
    parser = optparse.OptionParser(
        usage="%prog [options] parameter_file ...", version=freephil.__version__
    )
    parser.add_option("-?", action="help", help=optparse.SUPPRESS_HELP)
    parser.add_option(
        "--diff",
        action="store_true",
        help="Display only differences between the first file (master)"
        " and the combined definitions from all other files.",
    )
    parser.add_option(
        "--show_help",
        action="store_true",
        help="Display help for each parameter if available.",
    )
    parser.add_option(
        "--show_some_attributes",
        action="store_true",
        help="Display non-default attributes for each parameter.",
    )
    parser.add_option(
        "--show_all_attributes",
        action="store_true",
        help="Display all attributes for each parameter.",
    )
    parser.add_option(
        "--process_includes",
        action="store_true",
        help="Inline include files.",
    )
    parser.add_option(
        "--print_width",
        action="store",
        type="int",
        help="Width for output",
        metavar="INT",
    )
    parser.add_option(
        "--print_prefix",
        action="store",
        type="string",
        default="",
        help="Prefix string for output",
    )
    options, args = parser.parse_args()
    if not args:
        parser.print_help()
        return

    attributes_level = 0
    if options.show_all_attributes:
        attributes_level = 3
    elif options.show_some_attributes:
        attributes_level = 2
    elif options.show_help:
        attributes_level = 1
    prefix = options.print_prefix

    def parse(file_name):
        return freephil.parse(
            file_name=file_name,
            process_includes=options.process_includes,
        )

    def show(scope):
        scope.show(
            out=sys.stdout,
            prefix=prefix,
            attributes_level=attributes_level,
            print_width=options.print_width,
        )

    if options.diff:
        if len(args) < 2:
            parser.error("Option --diff requires at least two file names.")
        master = parse(file_name=args[0])
        show(
            scope=master.fetch_diff(
                sources=[parse(file_name=file_name) for file_name in args[1:]]
            )
        )
    else:
        for file_name in args:
            print(prefix.rstrip())
            show(scope=parse(file_name))
            print(prefix.rstrip())
