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

from diffoscope.comparators.ar import ArFile

from utils.data import load_fixture, get_data
from utils.tools import skip_unless_tools_exist
from utils.nonexisting import assert_non_existing

ar1 = load_fixture('test3.a')
ar2 = load_fixture('test4.a')

def test_identification(ar1):
    assert isinstance(ar1, ArFile)

def test_no_differences(ar1):
    difference = ar1.compare(ar1)
    assert difference is None

@pytest.fixture
def differences(ar1, ar2):
    return ar1.compare(ar2).details

def test_compare_non_existing(monkeypatch, ar1):
    assert_non_existing(monkeypatch, ar1)

@skip_unless_tools_exist('nm')
def test_filelist(differences):
    assert differences[0].source1 == 'file list'
    assert differences[0].source2 == 'file list'
    expected_diff = get_data('ar_filelist_expected_diff')
    assert differences[0].unified_diff == expected_diff

@skip_unless_tools_exist('nm')
def test_content(differences):
    assert differences[1].source1 == 'a.txt'
    assert differences[1].source2 == 'a.txt'
    expected_diff = get_data('ar_content_expected_diff')
    assert differences[1].unified_diff == expected_diff
