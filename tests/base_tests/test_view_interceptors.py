import time
from typing import List

import pytest

from slim.base.sqlquery import DataRecord, SQLQueryInfo, SQL_OP
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
    user_id = BlobField(default=None, null=True)

    class Meta:
        database = db


db.create_tables([Topic], safe=True)


Topic.create(time=time.time(), title='Hello', content='World', user_id=b'11')
Topic.create(time=time.time(), title='Hello2', content='World', user_id=b'22')
Topic.create(time=time.time(), title='Hello3', content='World', user_id=b'33')


@app.route.view('/topic')
class TopicView(PeeweeView):
    model = Topic

    async def after_read(self, records: List[DataRecord]):
        for i in records:
            i['after_read'] = 1
        await super().after_read(records)


@app.route.view('/topic2')
class TopicView2(PeeweeView):
    model = Topic

    async def before_query(self, info: SQLQueryInfo):
        info.add_condition('user_id', SQL_OP.IN, [b'11'])


@app.route.view('/topic3')
class TopicView3(PeeweeView):
    model = Topic

    async def before_query(self, info: SQLQueryInfo):
        info.add_condition('xxxx', SQL_OP.IN, [b'11'])


app.prepare()


async def test_after_read_get():
    view = await invoke_interface(app, TopicView().get)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'].get('after_read')  # 不知道为啥 assert in 的写法会卡住


async def test_after_read_list():
    view = await invoke_interface(app, TopicView().list)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    for i in view.ret_val['data']['items']:
        assert i.get('after_read')


async def test_before_query():
    view = await invoke_interface(app, TopicView2().get)
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_before_query_bad_condition():
    with pytest.raises(AssertionError):
        await invoke_interface(app, TopicView3().get)
