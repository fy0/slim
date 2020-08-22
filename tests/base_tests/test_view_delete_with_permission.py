import time

import pytest

from slim.base.permission import Ability, A
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION, EMPTY_PERMISSION
from slim.tools.test import invoke_interface

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=EMPTY_PERMISSION)
db = SqliteDatabase(":memory:")


class Topic(Model):
    title = CharField(index=True, max_length=255)
    time = BigIntegerField(index=True, default=time.time)
    content = TextField()

    class Meta:
        table_name = 'topic'
        database = db


class Article(Model):
    name = CharField(index=True, max_length=255)
    content = TextField()

    class Meta:
        table_name = 'article'
        database = db


db.create_tables([Topic, Article], safe=True)

Topic.create(title='Hello1', content='World')
Topic.create(title='Hello2', content='World')
Topic.create(title='Hello3', content='World')
Topic.create(title='Hello4', content='World')
Article.create(name='Hello', content='World')
Article.create(name='Hello2', content='World2')
Article.create(name='Hello3', content='World3')


app.permission.add(None, Ability({
    'topic': {
        '|': {A.QUERY},
        'title': {A.QUERY, A.READ},
        'time': {A.QUERY, A.READ, A.QUERY_EX},
        'content': {A.QUERY},
    },
    'article': {
        '|': {A.QUERY, A.DELETE},
        'name': {A.QUERY, A.READ},
        'content': {A.QUERY},
    }
}))


@app.route.view('/topic')
class TopicView(PeeweeView):
    model = Topic


@app.route.view('/article')
class ArticleView(PeeweeView):
    model = Article


app.prepare()


async def test_delete_bad():
    resp = await invoke_interface(app, TopicView().delete, params={'id': 1})
    assert resp.ret_val['code'] == RETCODE.PERMISSION_DENIED


async def test_delete_permitted():
    resp = await invoke_interface(app, ArticleView().delete, params={'id': 1})
    assert resp.ret_val['code'] == RETCODE.SUCCESS
