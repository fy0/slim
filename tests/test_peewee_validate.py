import pytest
from peewee import SqliteDatabase, Model, BlobField, IntegerField, FloatField, TextField, BooleanField
from playhouse.sqlite_ext import JSONField as SQLITE_JSONField
from schematics.exceptions import DataError

from slim.support.peewee.validate import get_pv_model_info

pytestmark = [pytest.mark.asyncio]


db = SqliteDatabase(":memory:")


class ATestModel(Model):
    num1 = IntegerField()
    num2 = FloatField()
    hex = BlobField()
    str1 = TextField()
    bool = BooleanField()
    ex = SQLITE_JSONField()

    class Meta:
        table_name = 'test'
        database = db


async def test_base_types():
    base = {
        'num1': 123,
        'num2': 123.45,
        'str1': 'whatever',
        'hex': 'aabb',
        'bool': True
    }

    info = get_pv_model_info(ATestModel)
    cls = info['data_model']
    c = cls(base)
    assert c.to_native()['hex'] == b'\xaa\xbb'

    with pytest.raises(DataError):
        d = base.copy()
        d['hex'] = 'qwer'
        cls(d)

    d = base.copy()
    d['bool'] = '1'
    cls(d)

    with pytest.raises(DataError):
        d = base.copy()
        d['bool'] = 't'
        cls(d)

    with pytest.raises(DataError):
        d = base.copy()
        d['str1'] = {}
        cls(d)
