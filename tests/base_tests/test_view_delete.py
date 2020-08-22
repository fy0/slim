import time

import pytest

from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from slim.tools.test import invoke_interface

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


async def test_delete_simple():
    resp = await invoke_interface(app, TopicView().delete, params={'id': 1})
    assert resp.ret_val['code'] == RETCODE.SUCCESS
