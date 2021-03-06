#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2014-2015 Jérémy Bobbio <lunar@debian.org>
# Copyright © 2017 Chris Lamb <lamby@debian.org>
#
# diffoscope is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# diffoscope is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with diffoscope.  If not, see <https://www.gnu.org/licenses/>.

import os
import sys
import signal
import logging
import argparse
import traceback

from . import VERSION
from .path import set_path
from .tools import tool_prepend_prefix, tool_required, OS_NAMES, get_current_os
from .config import Config
from .locale import set_locale
from .logging import setup_logging
from .progress import ProgressManager, Progress
from .profiling import ProfileManager, profile
from .tempfiles import clean_all_temp_files
from .difference import Difference
from .comparators import ComparatorManager
from .external_tools import EXTERNAL_TOOLS
from .presenters.html import JQUERY_SYSTEM_LOCATIONS
from .presenters.formats import PresenterManager
from .comparators.utils.compare import compare_root_paths
from .readers import load_diff, load_diff_from_path

logger = logging.getLogger(__name__)


try:
    import tlsh
except ImportError:
    tlsh = None

try:
    import argcomplete
except ImportError:
    argcomplete = None


class BooleanAction(argparse.Action):

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError("nargs not allowed for BooleanAction")
        super(BooleanAction, self).__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, not option_string.startswith("--no"))


def create_parser():
    parser = argparse.ArgumentParser(
        description='Calculate differences between two files or directories',
        add_help=False)
    parser.add_argument('path1', nargs='?', help='First file or directory to '
                        'compare. If omitted, tries to read a diffoscope diff from stdin.')
    parser.add_argument('path2', nargs='?', help='Second file or directory to '
                        'compare. If omitted, no comparison is done but instead we read a '
                        'diffoscope diff from path1 and will output this in the formats '
                        'specified by the rest of the command line.')
    parser.add_argument('--debug', action='store_true',
                        default=False, help='Display debug messages')
    parser.add_argument('--debugger', action='store_true',
                        help='Open the Python debugger in case of crashes')
    parser.add_argument('--status-fd', metavar='FD', type=int,
                        help='Send machine-readable status to file descriptor FD')
    parser.add_argument('--progress', '--no-progress', action=BooleanAction, default=None,
                        help='Show an approximate progress bar. Default: yes if '
                        'stdin is a tty, otherwise no.')
    parser.add_argument('--no-default-limits', action='store_true', default=False,
                        help='Disable most default output limits and diff calculation limits.')

    group1 = parser.add_argument_group('output types')
    group1.add_argument('--text', metavar='OUTPUT_FILE', dest='text_output',
                        help='Write plain text output to given file (use - for stdout)')
    group1.add_argument('--text-color', metavar='WHEN', default='auto',
                        choices=['never', 'auto', 'always'],
                        help='When to output color diff. WHEN is one of {%(choices)s}. '
                        'Default: auto, meaning yes if the output is a terminal, otherwise no.')
    group1.add_argument('--output-empty', action='store_true',
                        help='If there was no difference, then output an empty '
                        'diff for each output type that was specified. In '
                        '--text output, an empty file is written.')
    group1.add_argument('--html', metavar='OUTPUT_FILE', dest='html_output',
                        help='Write HTML report to given file (use - for stdout)')
    group1.add_argument('--html-dir', metavar='OUTPUT_DIR', dest='html_output_directory',
                        help='Write multi-file HTML report to given directory')
    group1.add_argument('--css', metavar='URL', dest='css_url',
                        help='Link to an extra CSS for the HTML report')
    group1.add_argument('--jquery', metavar='URL', dest='jquery_url',
                        help='URL link to jQuery, for --html and --html-dir output. '
                        'If this is a non-existent relative URL, diffoscope will create a '
                        'symlink to a system installation. (Paths searched: %s.) '
                        'If not given, --html output will not use JS but --html-dir will '
                        'if it can be found; give "disable" to disable JS on all outputs.' %
                        ', '.join(JQUERY_SYSTEM_LOCATIONS))
    group1.add_argument('--json', metavar='OUTPUT_FILE', dest='json_output',
                        help='Write JSON text output to given file (use - for stdout)')
    group1.add_argument('--markdown', metavar='OUTPUT_FILE', dest='markdown_output',
                        help='Write Markdown text output to given file (use - for stdout)')
    group1.add_argument('--restructured-text', metavar='OUTPUT_FILE',
                        dest='restructuredtext_output',
                        help='Write RsT text output to given file (use - for stdout)')
    group1.add_argument('--profile', metavar='OUTPUT_FILE', dest='profile_output',
                        help='Write profiling info to given file (use - for stdout)')

    group2 = parser.add_argument_group('output limits')
    # everything marked with default=None below is affected by no-default-limits
    group2.add_argument('--max-text-report-size', metavar='BYTES', type=int,
                        help='Maximum bytes written in --text report. (0 to '
                        'disable, default: %d)' % Config().max_text_report_size,
                        default=None)
    group2.add_argument('--max-report-size', metavar='BYTES', type=int,
                        help='Maximum bytes of a report in a given format, '
                        'across all of its pages. Note that some formats, such '
                        'as --html, may be restricted by even smaller limits '
                        'such as --max-page-size. (0 to disable, default: %d)' %
                        Config().max_report_size, default=None).completer=RangeCompleter(
                        Config().max_report_size)
    group2.add_argument('--max-diff-block-lines', metavar='LINES', type=int,
                        help='Maximum number of lines output per unified-diff '
                        'block, across all pages. (0 to disable, default: %d)' %
                        Config().max_diff_block_lines, default=None).completer=RangeCompleter(
                        Config().max_diff_block_lines)
    group2.add_argument('--max-page-size', metavar='BYTES', type=int,
                        help='Maximum bytes of the top-level (--html-dir) or sole '
                        '(--html) page. (default: %(default)s, remains in effect '
                        'even with --no-default-limits)', default=
                        Config().max_page_size).completer=RangeCompleter(
                        Config().max_page_size)
    group2.add_argument('--max-page-size-child', metavar='BYTES', type=int,
                        help='In --html-dir output, this is the maximum bytes of '
                        'each child page (default: %(default)s, remains in '
                        'effect even with --no-default-limits)', default=str(
                        Config().max_page_size_child)).completer=RangeCompleter(
                        Config().max_page_size_child)
    # TODO: old flag kept for backwards-compat, drop 6 months after v84
    group2.add_argument('--max-report-size-child', metavar='BYTES', type=int,
                        help=argparse.SUPPRESS, default=None)
    group2.add_argument('--max-page-diff-block-lines', metavar='LINES', type=int,
                        help='Maximum number of lines output per unified-diff block '
                        'on the top-level (--html-dir) or sole (--html) page, before '
                        'spilling it into child pages (--html-dir) or skipping the '
                        'rest of the diff block. Child pages are limited instead by '
                        '--max-page-size-child. (default: %(default)s, remains in '
                        'effect even with --no-default-limits)', default=
                        Config().max_page_diff_block_lines).completer=RangeCompleter(
                        Config().max_page_diff_block_lines)
    # TODO: old flag kept for backwards-compat, drop 6 months after v84
    group2.add_argument("--max-diff-block-lines-parent", metavar='LINES', type=int,
                        help=argparse.SUPPRESS, default=None)

    group3 = parser.add_argument_group('diff calculation')
    group3.add_argument('--new-file', action='store_true',
                        help='Treat absent files as empty')
    group3.add_argument('--exclude', dest='excludes',
                        metavar='GLOB_PATTERN', action='append', default=[],
                        help='Exclude files that match %(metavar)s')
    group3.add_argument('--exclude-command', dest='exclude_commands',
                        metavar='REGEX_PATTERN', action='append', default=[],
                        help='Exclude commands that match %(metavar)s. For '
                        "example, '^readelf.*\s--debug-dump=info' takes by far "
                        'the longest time, and differences here are probably '
                        'only secondary differences caused by something that '
                        'is already represented elsewhere in the diff.')
    group3.add_argument('--exclude-directory-metadata', '--no-exclude-directory-metadata',
                        action=BooleanAction, default=False,
                        help='Exclude directory metadata. Useful if comparing '
                        'files whose filesystem-level metadata is not intended '
                        'to be distributed to other systems. For example, this '
                        'is true for most distros\' package builders, but not '
                        'true for the output of commands like `make install`. '
                        'Metadata of archive members remain un-excluded. '
                        'Default: %(default)s')
    group3.add_argument('--fuzzy-threshold', type=int,
                        help='Threshold for fuzzy-matching '
                        '(0 to disable, %(default)s is default, 400 is high fuzziness)',
                        default=Config().fuzzy_threshold).completer=RangeCompleter(400)
    group3.add_argument('--tool-prefix-binutils', metavar='PREFIX',
                        help='Prefix for binutils program names, e.g. '
                        '"aarch64-linux-gnu-" for a foreign-arch binary or "g" '
                        'if you\'re on a non-GNU system.')
    group3.add_argument('--max-diff-input-lines', metavar='LINES', type=int,
                        help='Maximum number of lines fed to diff(1) '
                        '(0 to disable, default: %d)' %
                        Config().max_diff_input_lines,
                        default=None).completer=RangeCompleter(
                        Config().max_diff_input_lines)
    group3.add_argument('--max-container-depth', metavar='DEPTH', type=int,
                        help='Maximum depth to recurse into containers. '
                        '(Cannot be disabled for security reasons, default: '
                        '%(default)s)',
                        default=Config().max_container_depth)
    group3.add_argument('--max-diff-block-lines-saved', metavar='LINES', type=int,
                        help='Maximum number of lines saved per diff block. '
                        'Most users should not need this, unless you run out '
                        'of memory. This truncates diff(1) output before emitting '
                        'it in a report, and affects all types of output, '
                        'including --text and --json. (0 to disable, default: '
                        '%(default)s)', default=0)
    group3.add_argument('--force-details', default=False, action='store_true',
                        help='Force recursing into the depths of file formats '
                        'even if files have the same content, only really '
                        'useful for debugging diffoscope. Default: %(default)s')

    group4 = parser.add_argument_group('information commands')
    group4.add_argument('--help', '-h', action='help',
                        help="Show this help and exit")
    group4.add_argument('--version', action='version',
                        version='diffoscope %s' % VERSION,
                        help="Show program's version number and exit")
    group4.add_argument('--list-tools', nargs='?', type=str, action=ListToolsAction,
                        metavar='DISTRO', choices=OS_NAMES,
                        help='Show external tools required and exit. '
                        'DISTRO can be one of {%(choices)s}. '
                        'If specified, the output will list packages in that '
                        'distribution that satisfy these dependencies.')
    group4.add_argument('--list-debian-substvars', action=ListDebianSubstvarsAction,
                        help="List packages needed for Debian in 'substvar' format.")

    if not tlsh:
        parser.epilog = 'File renaming detection based on fuzzy-matching is currently disabled. It can be enabled by installing the "tlsh" module available at https://github.com/trendmicro/tlsh'
    if argcomplete:
        argcomplete.autocomplete(parser)
    elif '_ARGCOMPLETE' in os.environ:
        logger.error('Argument completion requested but the "argcomplete" module is not installed. It can be obtained at https://pypi.python.org/pypi/argcomplete')
        sys.exit(1)

    def post_parse(parsed_args):
        if parsed_args.path2 is None:
            # warn about unusual flags in this mode
            ineffective_flags = [f
                                 for x in group3._group_actions
                                 if getattr(parsed_args, x.dest) != x.default
                                 for f in x.option_strings]
            if ineffective_flags:
                logger.warning("Loading diff instead of calculating it, but diff-calculation flags were given; they will be ignored:")
                logger.warning(ineffective_flags)
    return parser, post_parse


class RangeCompleter(object):
    def __init__(self, start, end=0, divisions=16):
        if end < start:
            tmp = end
            end = start
            start = tmp
        self.choices = range(start, end + 1, int((end-start+1)/divisions))

    def __call__(self, prefix, **kwargs):
        return (str(i) for i in self.choices if str(i).startswith(prefix))


class ListToolsAction(argparse.Action):
    def __call__(self, parser, namespace, os_override, option_string=None):
        # Ensure all comparators are imported so tool_required.all is
        # populated.
        ComparatorManager().reload()

        print("External-Tools-Required: ", end='')
        print(', '.join(sorted(tool_required.all)))
        if os_override:
            os_list = [os_override]
        else:
            current_os = get_current_os()
            os_list = [current_os] if (current_os in OS_NAMES) else iter(OS_NAMES)
        for os in os_list:
            tools = set()
            print("Available-in-{}-packages: ".format(OS_NAMES[os]), end='')
            for x in tool_required.all:
                try:
                    tools.add(EXTERNAL_TOOLS[x][os])
                except KeyError:
                    pass
            print(', '.join(sorted(tools)))
        sys.exit(0)


class ListDebianSubstvarsAction(argparse._StoreTrueAction):
    def __call__(self, *args, **kwargs):
        # Ensure all comparators are imported so tool_required.all is
        # populated.
        ComparatorManager().reload()

        tools = set()
        for x in tool_required.all:
            try:
                tools.add(EXTERNAL_TOOLS[x]['debian'])
            except KeyError:
                pass

        # Exclude "Required" packages
        for x in (
            'gzip',
            'tar',
            'coreutils',
            'diffutils',
            'e2fsprogs',
            'findutils',
        ):
            tools.discard(x)

        print('diffoscope:Recommends={}'.format(', '.join(sorted(tools))))
        sys.exit(0)


def maybe_set_limit(config, parsed_args, key):
    # apply limits affected by "no-default-limits"
    v = getattr(parsed_args, key)
    if v is not None:
        setattr(config, key, float("inf") if v == 0 else v)
    elif parsed_args.no_default_limits:
        setattr(config, key, float("inf"))


def run_diffoscope(parsed_args):
    ProfileManager().setup(parsed_args)
    PresenterManager().configure(parsed_args)
    logger.debug("Starting diffoscope %s", VERSION)
    if not tlsh and Config().fuzzy_threshold != parsed_args.fuzzy_threshold:
        logger.warning('Fuzzy-matching is currently disabled as the "tlsh" module is unavailable.')
    maybe_set_limit(Config(), parsed_args, "max_report_size")
    maybe_set_limit(Config(), parsed_args, "max_text_report_size")
    maybe_set_limit(Config(), parsed_args, "max_diff_block_lines")
    Config().max_page_size = parsed_args.max_page_size
    # TODO: old flag kept for backwards-compat, drop 6 months after v84
    if parsed_args.max_report_size_child is not None:
        logger.warning("Detected deprecated flag --max-report-size-child; use --max-page-size-child instead.")
        Config().max_page_size_child = parsed_args.max_report_size_child
    Config().max_page_size_child = parsed_args.max_page_size_child
    # TODO: old flag kept for backwards-compat, drop 6 months after v84
    if parsed_args.max_diff_block_lines_parent is not None:
        logger.warning("Detected deprecated flag --max-diff-block-lines-parent; use --max-page-diff-block-lines instead.")
        logger.warning("Note that the new flag --max-page-diff-block-lines also applies to --html output.")
        Config().max_page_diff_block_lines = parsed_args.max_diff_block_lines_parent
    Config().max_page_diff_block_lines = parsed_args.max_page_diff_block_lines

    maybe_set_limit(Config(), parsed_args, "max_diff_block_lines_saved")
    maybe_set_limit(Config(), parsed_args, "max_diff_input_lines")
    Config().max_container_depth = parsed_args.max_container_depth
    Config().force_details = parsed_args.force_details
    Config().fuzzy_threshold = parsed_args.fuzzy_threshold
    Config().new_file = parsed_args.new_file
    Config().excludes = parsed_args.excludes
    Config().exclude_commands = parsed_args.exclude_commands
    Config().exclude_directory_metadata = parsed_args.exclude_directory_metadata
    Config().compute_visual_diffs = PresenterManager().compute_visual_diffs()
    Config().check_constraints()
    tool_prepend_prefix(parsed_args.tool_prefix_binutils, *"ar as ld ld.bfd nm objcopy objdump ranlib readelf strip".split())
    set_path()
    set_locale()
    path1, path2 = parsed_args.path1, parsed_args.path2
    if path2 is None:
        logger.debug("Loading diff from stdin")
        if path1 is None or path1 == '-':
            difference = load_diff(sys.stdin, "stdin")
        else:
            difference = load_diff_from_path(path1)
    else:
        logger.debug('Starting comparison')
        with Progress():
            with profile('main', 'outputs'):
                difference = compare_root_paths(path1, path2)
        ProgressManager().finish()
    # Generate an empty, dummy diff to write, saving the exit code first.
    has_differences = bool(difference is not None)
    if difference is None and parsed_args.output_empty:
        difference = Difference(None, path1, path2)
    with profile('main', 'outputs'):
        PresenterManager().output(difference, parsed_args, has_differences)
    return 1 if has_differences else 0


def sigterm_handler(signo, stack_frame):
    clean_all_temp_files()
    os._exit(2)


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    signal.signal(signal.SIGTERM, sigterm_handler)
    parsed_args = None
    try:
        with profile('main', 'parse_args'):
            parser, post_parse = create_parser()
            parsed_args = parser.parse_args(args)
        log_handler = ProgressManager().setup(parsed_args)
        with setup_logging(parsed_args.debug, log_handler) as logger:
            post_parse(parsed_args)
            sys.exit(run_diffoscope(parsed_args))
    except KeyboardInterrupt:
        logger.info('Keyboard Interrupt')
        sys.exit(2)
    except BrokenPipeError:
        sys.exit(2)
    except Exception:
        traceback.print_exc()
        if parsed_args and parsed_args.debugger:
            import pdb
            pdb.post_mortem()
        sys.exit(2)
    finally:
        with profile('main', 'cleanup'):
            clean_all_temp_files()

        # Print profiling output at the very end
        if parsed_args is not None:
            ProfileManager().finish(parsed_args)


if __name__ == '__main__':
    main()
