import os
import re

import slim


def test_version():
    setup_file = open(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'setup.py')), 'r', encoding='utf-8').read()

    m = re.search(r"version='(.+?)',", setup_file)
    assert m.group(1) == slim.__version__


if __name__ == '__main__':
    test_version()
