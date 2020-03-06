import json

import pytest
from unittest import mock
from aiohttp.test_utils import make_mocked_request
from multidict import MultiDict

from slim.base.user import BaseUserViewMixin
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    info = BlobField()

    class Meta:
        table_name = 'test'
        database = db


@app.route('test')
class ATestView(PeeweeView):
    model = ATestModel


db.create_tables([ATestModel])


async def test_post_blob():
    request = make_mocked_request('POST', '/api/test', headers={},
                                  protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    request._post = dict(info='aabbcc')
    view = ATestView(app, request)
    await view._prepare()
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    request._post = dict(info='a')  # 0x0A
    view = ATestView(app, request)
    await view._prepare()
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    view = ATestView(app, request)
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['info'] == b'\xaa\xbb\xcc'

    request = make_mocked_request('POST', '/api/test',
                                  headers={'content-type': 'application/json'},
                                  protocol=mock.Mock(), app=app)
    raw_json = json.dumps({'info': 'aabbcc'})
    request._post = raw_json
    request._read_bytes = bytes(raw_json, encoding='utf-8')
    view = ATestView(app, request)
    await view._prepare()
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS