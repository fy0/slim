import peewee
import pytest
from multidict import MultiDict
from peewee import SqliteDatabase, CharField, BigIntegerField, TextField
from schematics import Model
from schematics.types import StringType

from slim import Application, ALL_PERMISSION
from slim.base._view.base_view import BaseView
from slim.base._view.validate import view_validate_check
from slim.base.types import BuiltinInterface
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from slim.tools.test import make_mocked_view

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class Topic(peewee.Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True)
    content = TextField()

    class Meta:
        database = db


db.create_tables([Topic], safe=True)


@app.route.view('test1')
class ATestView(PeeweeView):
    model = Topic


class InputModel(Model):
    name = StringType(required=True)


async def test_va_query_success():
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', params={'name': 'Alice'})
    await view_validate_check(view, InputModel, None)


async def test_va_query_success_multi_dict():
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', params=MultiDict({'name': 'Alice'}))
    await view_validate_check(view, InputModel, None)
    assert view.ret_val is None


async def test_va_query_failed():
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', params={'name': []})
    await view_validate_check(view, InputModel, None)
    assert view.ret_val and  view.ret_val['code'] == RETCODE.INVALID_PARAMS


async def test_va_query_failed2():
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', params={})
    await view_validate_check(view, InputModel, None)
    assert view.ret_val and  view.ret_val['code'] == RETCODE.INVALID_PARAMS


async def test_va_post_success():
    view = await make_mocked_view(app, ATestView, 'POST', '/api/test1', post={'name': 'Bob'})
    await view_validate_check(view, None, InputModel)
    assert view.ret_val is None


async def test_va_post_failed():
    view = await make_mocked_view(app, ATestView, 'POST', '/api/test1', params={'name': []})
    await view_validate_check(view, None, InputModel)
    assert view.ret_val
    assert view.ret_val['code'] == RETCODE.INVALID_POSTDATA


class WriteValueModel(Model):
    name = StringType(required=True)


async def test_va_write_value_bulk_success():
    view = await make_mocked_view(app, ATestView, 'POST', '/api/test1', post={'items': [
        {"name": '123'},
        {"name": '456'},
    ]})
    view.current_interface = BuiltinInterface.BULK_INSERT
    await view_validate_check(view, None, None, va_write_value=WriteValueModel)
    assert view.ret_val is None, 'no error raised'
    assert view._.validated_write_values
    assert view._.validated_write_values[0].name == '123'


async def test_va_write_value_set_or_update_success():
    view = await make_mocked_view(app, ATestView, 'POST', '/api/test1', post={"name": '123'})
    view.current_interface = BuiltinInterface.SET
    await view_validate_check(view, None, None, va_write_value=WriteValueModel)
    assert view.ret_val is None, 'no error raised'
    assert view._.validated_write_values
    assert view._.validated_write_values[0].name == '123'
