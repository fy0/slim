import pytest
from multidict import MultiDict
from schematics import Model
from schematics.types import StringType

from slim import Application, ALL_PERMISSION
from slim.base._view.base_view import BaseView
from slim.base._view.validate import view_validate_check
from slim.retcode import RETCODE
from slim.tools.test import make_mocked_view_instance

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)


@app.route('test1')
class ATestView(BaseView):
    pass


class InputModel(Model):
    name = StringType(required=True)


async def test_va_query_success():
    view = await make_mocked_view_instance(app, ATestView, 'GET', '/api/test1', params={'name': 'Alice'})
    await view_validate_check(view, InputModel, None)


async def test_va_query_success_multi_dict():
    view = await make_mocked_view_instance(app, ATestView, 'GET', '/api/test1', params=MultiDict({'name': 'Alice'}))
    await view_validate_check(view, InputModel, None)
    assert view.ret_val is None


async def test_va_query_failed():
    view = await make_mocked_view_instance(app, ATestView, 'GET', '/api/test1', params={'name': []})
    await view_validate_check(view, InputModel, None)
    assert view.ret_val and  view.ret_val['code'] == RETCODE.INVALID_PARAMS


async def test_va_query_failed2():
    view = await make_mocked_view_instance(app, ATestView, 'GET', '/api/test1', params={})
    await view_validate_check(view, InputModel, None)
    assert view.ret_val and  view.ret_val['code'] == RETCODE.INVALID_PARAMS


async def test_va_post_success():
    view = await make_mocked_view_instance(app, ATestView, 'POST', '/api/test1', post={'name': 'Bob'})
    await view_validate_check(view, None, InputModel)
    assert view.ret_val is None


async def test_va_post_failed():
    view = await make_mocked_view_instance(app, ATestView, 'POST', '/api/test1', params={'name': []})
    await view_validate_check(view, None, InputModel)
    assert view.ret_val and view.ret_val['code'] == RETCODE.INVALID_POSTDATA
