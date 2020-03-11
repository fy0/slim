from slim.utils.autoload import import_path
from tests.utils_test import autoload


def test_import_path():
    assert autoload.FLAG == 1
    import_path('tests/utils_test/autoload')
    assert autoload.FLAG == 2
