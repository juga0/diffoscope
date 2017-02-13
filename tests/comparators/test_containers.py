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

from diffoscope.comparators.utils.compare import compare_files

from utils.data import data, load_fixture, get_data
from utils.tools import skip_unless_tools_exist

test_tar_gz = load_fixture('test1.tar.gz')
test_zip_bz2 = load_fixture('test2.zip.bz2')
test_zip = load_fixture('test2.zip')
test_tar = load_fixture('test1.tar')
test_cpio = load_fixture('test2.cpio')

@pytest.fixture
def differences_containers(test_tar, test_cpio):
    return compare_files(test_tar, test_cpio).details

@pytest.fixture
def differences_nested(test_tar_gz, test_zip_bz2):
    return compare_files(test_tar_gz, test_zip_bz2).details

@pytest.fixture
def differences_different_levels(test_tar_gz, test_zip):
    return compare_files(test_tar_gz, test_zip).details

@skip_unless_tools_exist('cpio')
def test_file_list(differences_containers):
    expected_diff = get_data('containers_filelist_expected_diff')
    assert differences_containers[1].source1 == 'file list'
    assert differences_containers[1].source2 == 'file list'
    assert differences_containers[1].unified_diff == expected_diff

@skip_unless_tools_exist('cpio')
def test_types(differences_containers):
    expected_diff = get_data('containers_types_expected_diff')
    assert differences_containers[0].source1 == 'container type'
    assert differences_containers[0].source2 == 'container type'
    assert differences_containers[0].unified_diff == expected_diff

@skip_unless_tools_exist('cpio')
def test_content(differences_containers):
    expected_diff = get_data('text_ascii_expected_diff')
    assert differences_containers[2].unified_diff == expected_diff

@skip_unless_tools_exist('bzip2', 'gzip', 'zipinfo')
def test_types_nested(differences_nested):
    expected_diff = get_data('nested_containers_types_expected_diff')
    assert differences_nested[0].source1 == 'container type'
    assert differences_nested[0].source2 == 'container type'
    assert differences_nested[0].unified_diff == expected_diff

@skip_unless_tools_exist('bzip2', 'gzip', 'zipinfo')
def test_types_nested1(differences_nested):
    expected_diff1 = get_data('nested_containers_types_expected_diff1')
    assert differences_nested[2].details[0].source1 == 'container type'
    assert differences_nested[2].details[0].source2 == 'container type'
    assert differences_nested[2].details[0].unified_diff == expected_diff1

@skip_unless_tools_exist('bzip2', 'gzip', 'zipinfo')
def test_file_list_nested(differences_nested):
    expected_diff = get_data('nested_containers_filelist_expected_diff')
    assert differences_nested[1].source1 == 'file list'
    assert differences_nested[1].source2 == 'file list'
    assert differences_nested[1].unified_diff == expected_diff

@skip_unless_tools_exist('bzip2', 'gzip', 'zipinfo')
def test_file_list_nested2(differences_nested):
    expected_diff = get_data('nested_containers_filelist_expected_diff1')
    assert differences_nested[2].details[1].source1 == 'file list'
    assert differences_nested[2].details[1].source2 == 'file list'
    assert differences_nested[2].details[1].unified_diff == expected_diff

@skip_unless_tools_exist('bzip2', 'gzip', 'zipinfo')
def test_content_diff_nested(differences_nested):
    expected_diff = get_data('text_ascii_expected_diff')
    assert differences_nested[2].details[2].source1 == 'dir/text'
    assert differences_nested[2].details[2].source2 == 'dir/text'
    assert differences_nested[2].details[2].unified_diff == expected_diff

@skip_unless_tools_exist('gzip', 'zipinfo')
def test_types_different_levels(differences_different_levels):
    f = open(data('nested_containers_types_expected_diff2'), 'w')
    f.write(differences_different_levels[0].unified_diff)
    f.close()
    expected_diff = get_data('nested_containers_types_expected_diff2')
    assert differences_different_levels[0].source1 == 'container type'
    assert differences_different_levels[0].source2 == 'container type'
    assert differences_different_levels[0].unified_diff == expected_diff

@skip_unless_tools_exist('gzip', 'zipinfo')
def test_file_list_different_levels(differences_different_levels):
    expected_diff = get_data('nested_containers_filelist_expected_diff2')
    assert differences_different_levels[1].source1 == 'file list'
    assert differences_different_levels[1].source2 == 'file list'
    assert differences_different_levels[1].unified_diff == expected_diff

@skip_unless_tools_exist('gzip', 'zipinfo')
def test_content_diff_different_levels(differences_different_levels):
    expected_diff = get_data('text_ascii_expected_diff')
    assert differences_different_levels[2].source1 == 'dir/text'
    assert differences_different_levels[2].source2 == 'dir/text'
    assert differences_different_levels[2].unified_diff == expected_diff
