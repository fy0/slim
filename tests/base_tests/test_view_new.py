import time

import pytest

from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from slim.tools.test import make_mocked_view, invoke_interface

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True, default=time.time)
    content = TextField()

    class Meta:
        database = db


db.create_tables([Topic], safe=True)


Topic.create(time=time.time(), title='Hello', content='World')
Topic.create(time=time.time(), title='Hello2', content='World')
Topic.create(time=time.time(), title='Hello3', content='World')
Topic.create(time=time.time(), title='Hello4', content='World')


@app.route.view('/topic')
class TopicView(PeeweeView):
    model = Topic


app.prepare()


async def test_new_simple():
    post = {"title": '111', "content": "test"}
    view = await invoke_interface(app, TopicView().new, post=post)
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_new_bulk():
    items = [{"title": '111', "content": "test"}, {"title": '222', "content": "test"}]
    view = await invoke_interface(app, TopicView().bulk_insert, post={'items': items})
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_new_bulk_ignore():
    items = [{"id":1 ,"title": '111', "content": "test"}, {"title": '222', "content": "test"}]
    view = await invoke_interface(app, TopicView().bulk_insert, post={'items': items}, returning=True)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert len(view.ret_val['data']) == 1
