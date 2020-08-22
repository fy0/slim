import time

import pytest
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from slim.utils import get_ioloop
from slim.tools.test import make_mocked_view


pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    info = BlobField()

    class Meta:
        table_name = 'test'
        database = db


db.create_tables([ATestModel])


@app.route.view('test')
class ATestView(PeeweeView):
    LIST_PAGE_SIZE = -1

    model = ATestModel


async def test_view_list_bug():
    """
    当 LIST_PAGE_SIZE为-1 时，如果表中无数据，由于分页大小会自动设置为与查出的数据数量一致（为0），计算页数时会出现除以0的问题
    """
    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/list/1')
    await view.list()  # BUG 情况会抛出一个 ZeroDivisionError


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


@app.route.view('topic')
class TopicView(PeeweeView):
    model = Topic


async def test_list_items_exists():
    view: PeeweeView = await make_mocked_view(app, TopicView, 'POST', '/api/topic/list/1')
    await view.list()
    assert len(view.ret_val['data']['items']) == view.ret_val['data']['info']['items_count']
