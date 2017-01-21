# -*- coding: utf-8 -*-
#
# diffoscope: in-depth comparison of files, archives, and directories
#
# Copyright © 2017 Maria Glukhova <siammezzze@gmail.com>
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

import pytest

try:
    import tlsh
    tlsh_found = True
except ImportError:
    tlsh_found = False

from diffoscope.comparators.utils.compare import compare_files

from utils.data import data, load_fixture
from utils.tools import skip_unless_tools_exist

test_tar_gz = load_fixture('test1.tar.gz')
test_zip_bz2 = load_fixture('test1.tar.bz2')
test_tar = load_fixture('test3.tar')
test_cpio = load_fixture('test3.cpio')

@pytest.fixture
def differences_containers(test_tar, test_cpio):
    return compare_files(test_tar, test_cpio).details

@pytest.fixture
def differences_nested(test_tar_gz, test_zip_bz2):
    return compare_files(test_tar_gz, test_zip_bz2).details

@skip_unless_tools_exist('cpio')
def test_file_list(differences_containers):
    expected_diff = open(data('containers_filelist_expected_diff')).read()
    assert differences_containers[1].source1 == 'file list'
    assert differences_containers[1].source2 == 'file list'
    assert differences_containers[1].unified_diff == expected_diff

@skip_unless_tools_exist('cpio')
def test_types(differences_containers):
    expected_diff = open(data('containers_types_expected_diff')).read()
    assert differences_containers[0].source1 == 'container type'
    assert differences_containers[0].source2 == 'container type'
    assert differences_containers[0].unified_diff == expected_diff

@skip_unless_tools_exist('cpio')
def test_content(differences_containers):
    expected_diff = open(data('containers_content_expected_diff')).read()
    assert differences_containers[2].unified_diff == expected_diff

@skip_unless_tools_exist('bzip2', 'gzip', 'zipinfo')
@pytest.mark.skipif(not tlsh_found, reason='tlsh is missing')
def test_types_nested(differences_nested):
    expected_diff = \
        open(data('nested_containers_types_expected_diff')).read()
    assert differences_nested[0].source1 == 'container type'
    assert differences_nested[0].source2 == 'container type'
    assert differences_nested[0].unified_diff == expected_diff

@skip_unless_tools_exist('bzip2', 'gzip')
@pytest.mark.skipif(not tlsh_found, reason='tlsh is missing')
def test_file_list_nested2(differences_nested):
    expected_diff = \
        open(data('nested_containers_filelist_expected_diff')).read()
    assert differences_nested[1].details[0].source1 == 'file list'
    assert differences_nested[1].details[0].source2 == 'file list'
    assert differences_nested[1].details[0].unified_diff == expected_diff
