import json

from schematics import Model
from schematics.types import StringType, FloatType

from slim.utils.schematics_ext import JSONListType, JSONDictType, JSONType


def test_json_list():
    class MyModel(Model):
        a = JSONListType(StringType)

    a = MyModel({'a': [1, 2, 3]})
    a.validate()

    b = MyModel({'a': json.dumps([1, 2, 3])})
    b.validate()


def test_json_dict():
    class MyModel(Model):
        a = JSONDictType(StringType)

    a = MyModel({'a': {
        'a': 'b'
    }})
    a.validate()

    a = MyModel({'a': json.dumps({
        'a': 'b'
    })})
    a.validate()


def test_json_any():
    class MyModel(Model):
        a = JSONType()
        b = FloatType()

    a = MyModel({'a': {
        'a': 'b'
    }})
    a.validate()

    a = MyModel({'a': '{'})
    a.validate()

    a = MyModel({'a': json.dumps('{')})
    a.validate()

    a = MyModel({'a': [1, 2, 3]})
    a.validate()

    a = MyModel({'a': json.dumps([1, 2, 3]), 'b': '1'})
    a.validate()

    print(type(a.a))
    assert isinstance(a.a, list)
