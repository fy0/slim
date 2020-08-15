import time
from typing import List

import pytest
import schematics
from schematics.types import StringType

from slim.base.sqlquery import SQLValuesToWrite, DataRecord
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION, D
from slim.tools.test import invoke_interface


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


@app.route.view('/topic')
class TopicView(PeeweeView):
    model = Topic


class ChangeDataModel(schematics.Model):
    new_content = StringType()


@app.route.view('/topic2')
class TopicView2(PeeweeView):
    model = Topic

    @D.append_validate(va_post=ChangeDataModel)
    async def before_update(self, values: SQLValuesToWrite, records: List[DataRecord]):
        vpost: ChangeDataModel = self._.validated_post
        if vpost.new_content:
            values['content'] = vpost.new_content


async def test_set_simple():
    view = await invoke_interface(app, TopicView().set, params={'id': 1}, post={"content": "Content changed 3"})
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_set_bad_values():
    view = await invoke_interface(app, TopicView().set, params={'id': 1}, post={"asd": "1"})
    assert view.ret_val['code'] == RETCODE.INVALID_POSTDATA
    assert 'No value to set for table' in view.ret_val['data']


async def test_set_bulk():
    view = await invoke_interface(app, TopicView().set, post={"content": "Content changed 3"}, headers={'bulk': 'true'})
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'] == 4


async def test_set_with_empty_values():
    view = await invoke_interface(app, TopicView2().set, params={'id': 1}, post={"asd": "1"})
    assert view.ret_val['code'] == RETCODE.INVALID_POSTDATA
    assert 'No value to set for table' in view.ret_val['data']

    view = await invoke_interface(app, TopicView2().set, params={'id': 1}, post={"new_content": "1"})
    assert view.ret_val['code'] == RETCODE.SUCCESS
    t = Topic.get(Topic.id == 1)
    assert t.content == '1'


app.prepare()
