# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Maria Glukhova <siamezzze@gmail.com>
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
import pytest

from diffoscope.main import main

from comparators.utils.tools import skip_unless_tools_exist, \
    skip_if_binutils_does_not_support_x86, skip_unless_module_exists


def run(capsys, filenames, *args):
    with pytest.raises(SystemExit) as exc:
        main(args + tuple(
            os.path.join(os.path.dirname(__file__), 'data', x)
            for x in filenames
        ))

    out, err = capsys.readouterr()

    assert err == ''

    return exc.value.code, out

def test_hide_gzip_metadata(capsys):
    ret, out = run(capsys, ('test1.gz', 'test2.gz'),
                   '--hide-timestamp=gzip-metadata')

    assert ret == 1
    assert '── metadata' not in out
    assert '│   --- test1\n├── +++ test2' in out

@skip_unless_tools_exist('readelf', 'objdump', 'objcopy')
@skip_if_binutils_does_not_support_x86()
@skip_unless_module_exists('debian.deb822')
def test_hide_debugsym(capsys):
    ret, out = run(capsys, ('dbgsym/add/test-dbgsym_1_amd64.deb',
                            'dbgsym/mult/test-dbgsym_1_amd64.deb'),
                   '--hide-section=debug-symbols')

    assert ret == 1
    assert not any(['test-cases/dbgsym/package/test.c:2' in line for
                    line in out.split()])
