from slim.utils.autoload import import_path
from tests.utils_tests import autoload


def test_import_path():
    assert autoload.FLAG == 1
    import_path('tests/utils_tests/autoload')
    assert autoload.FLAG == 2
