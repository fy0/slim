import time

import pytest

from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from slim.tools.test import make_mocked_view_instance


pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True)
    content = TextField()

    class Meta:
        database = db


db.create_tables([Topic], safe=True)


Topic.create(time=time.time(), title='Hello', content='World')
Topic.create(time=time.time(), title='Hello2', content='World')
Topic.create(time=time.time(), title='Hello3', content='World')
Topic.create(time=time.time(), title='Hello4', content='World')


@app.route('/topic')
class TopicView(PeeweeView):
    model = Topic


async def test_set_simple():
    view: PeeweeView = await make_mocked_view_instance(app, TopicView, 'POST', '/api/topic/set', {'id': 1}, {"title": "Hello Again", "content": "Content changed"})
    await view.set()
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_set_bad_values():
    view: PeeweeView = await make_mocked_view_instance(app, TopicView, 'POST', '/api/topic/set', {'id': 1}, {"asd": 1})
    await view.set()
    assert view.ret_val['code'] == RETCODE.INVALID_POSTDATA
    assert 'Invalid post values' in view.ret_val['data']
