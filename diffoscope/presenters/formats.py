# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2016 Chris Lamb <lamby@debian.org>
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

import sys
import logging

from ..profiling import profile

from .text import TextPresenter
from .json import JSONPresenter
from .html import HTMLPresenter, HTMLDirectoryPresenter
from .markdown import MarkdownTextPresenter
from .restructuredtext import RestructuredTextPresenter

logger = logging.getLogger(__name__)


def configure_presenters(parsed_args):
    FORMATS = {
        'text': {
            'klass': TextPresenter,
            'target': parsed_args.text_output,
        },
        'html': {
            'klass': HTMLPresenter,
            'target': parsed_args.html_output,
        },
        'json': {
            'klass': JSONPresenter,
            'target': parsed_args.json_output,
        },
        'markdown': {
            'klass': MarkdownTextPresenter,
            'target': parsed_args.markdown_output,
        },
        'restructuredtext': {
            'klass': RestructuredTextPresenter,
            'target': parsed_args.restructuredtext_output,
        },
        'html_directory': {
            'klass': HTMLDirectoryPresenter,
            'target': parsed_args.html_output_directory,
        },
    }

    result = {k: v for k, v in FORMATS.items() if v['target'] is not None}

    # If no output specified, default to printing --text output to stdout
    if not result:
        parsed_args.text_output = FORMATS['text']['target'] = '-'
        result['text'] = FORMATS['text']

    logger.debug(
        "Will generate the following formats: %s", ", ".join(result.keys()),
    )

    return result


def output_all(config, difference, parsed_args, has_differences):
    for name, data in config.items():
        logger.debug("Generating %r output at %r", name, data['target'])

        with profile('output', name):
            data['klass'].run(data, difference, parsed_args, has_differences)
