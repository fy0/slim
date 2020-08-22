import json

import pytest
from unittest import mock
from multidict import MultiDict

from slim.base.user import BaseUserViewMixin
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from slim.tools.test import invoke_interface

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    info = BlobField()

    class Meta:
        table_name = 'test'
        database = db


@app.route.view('test')
class ATestView(PeeweeView):
    model = ATestModel


db.create_tables([ATestModel])

app.prepare()


async def test_post_blob():
    view = await invoke_interface(app, ATestView().get, content_type=None)
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    view = await invoke_interface(app, ATestView().new, post={'info': 'aabbcc'}, content_type=None)
    assert view.ret_val['code'] == RETCODE.SUCCESS

    view = await invoke_interface(app, ATestView().new, post={'info': 'a'}, content_type=None)  # 0x0A
    assert view.ret_val['code'] == RETCODE.SUCCESS

    view = await invoke_interface(app, ATestView().get)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['info'] == b'\xaa\xbb\xcc'

    view = await invoke_interface(app, ATestView().new, post={'info': 'aabbcc'})
    assert view.ret_val['code'] == RETCODE.SUCCESS
