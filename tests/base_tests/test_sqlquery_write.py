import pytest
from peewee import SqliteDatabase, Model, IntegerField, TextField, BlobField
from slim.base.permission import A

from slim import Application, ALL_PERMISSION
from slim.base.sqlquery import SQLValuesToWrite
from slim.exception import InvalidPostData
from slim.support.peewee import PeeweeView
from slim.tools.test import make_mocked_view

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    num1 = IntegerField()
    str1 = TextField()

    class Meta:
        table_name = 'test'
        database = db


@app.route.view('test')
class ATestView(PeeweeView):
    model = ATestModel


app.prepare()


async def test_value_write_normal():
    write = SQLValuesToWrite({
        'num1': 123,
        'str1': 'whatever'
    })
    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/list/1')
    write.bind(view, None, None)


async def test_value_write_normal2():
    write = SQLValuesToWrite({
        'num1': 123,
        'str1': 456
    })
    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/list/1')
    write.bind(view, None, None)
    assert write['str1'] == '456'


async def test_value_write_invalid():
    write = SQLValuesToWrite({
        'num1': 123,
        'str1': {}
    })
    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/list/1')
    with pytest.raises(InvalidPostData) as e:
        write.bind(view, None, None)


async def test_value_write_bind_with_empty():
    write = SQLValuesToWrite({
        '$num': 123
    })

    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/list/1')
    write.bind(view, None, None)
    assert len(write) == 0
