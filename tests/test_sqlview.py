import json

import pytest
from unittest import mock
from aiohttp.test_utils import make_mocked_request

from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application
from playhouse.sqlite_ext import JSONField as SQLITE_JSONField

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456')
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    name = TextField()
    binary = BlobField()
    count = IntegerField()
    active = BooleanField(default=False)
    flt = FloatField(default=0)
    json = SQLITE_JSONField()
    value = IntegerField(null=True)

    class Meta:
        db_table = 'test'
        database = db


class ATestBModel(Model):
    name = TextField()
    link = ForeignKeyField(ATestModel)

    class Meta:
        db_table = 'test2'
        database = db


class ATestCModel(Model):
    name = TextField()
    link = ForeignKeyField(ATestBModel)

    class Meta:
        db_table = 'test3'
        database = db


db.create_tables([ATestModel, ATestBModel, ATestCModel])
a1 = ATestModel.create(name='Name1', binary=b'test1', count=1, json={'q': 1, 'w1': 2})
a2 = ATestModel.create(name='Name2', binary=b'test2', count=2, json={'q': 1, 'w2': 2})
a3 = ATestModel.create(name='Name3', binary=b'test3', count=3, json={'q': 1, 'w3': 2})
a4 = ATestModel.create(name='Name4', binary=b'test4', count=4, json={'q': 1, 'w4': 2})
a5 = ATestModel.create(name='Name5', binary=b'test5', count=5, json={'q': 1, 'w5': 2})

b1 = ATestBModel.create(name='NameB1', link=a1)
b2 = ATestBModel.create(name='NameB2', link=a2)
b3 = ATestBModel.create(name='NameB3', link=a3)
b4 = ATestBModel.create(name='NameB4', link=a4)
b5 = ATestBModel.create(name='NameB5', link=a5)

c1 = ATestCModel.create(name='NameC1', link=b1)
c2 = ATestCModel.create(name='NameC2', link=b2)
c3 = ATestCModel.create(name='NameC3', link=b3)
c4 = ATestCModel.create(name='NameC4', link=b4)
c5 = ATestCModel.create(name='NameC5', link=b5)


@app.route('test1')
class ATestView(PeeweeView):
    model = ATestModel


@app.route('test2')
class ATestView2(PeeweeView):
    model = ATestBModel


@app.route('test3')
class ATestView3(PeeweeView):
    model = ATestCModel

    @classmethod
    def ready(cls):
        cls.add_soft_foreign_key('id', 'wrong table name')
        cls.add_soft_foreign_key('id', 'test2', 't2')
        cls.add_soft_foreign_key('id', 'test', 't1')


app._prepare()


async def test_bind():
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    assert len(view.model._meta.fields) == len(view.fields)
    assert set(view.model._meta.fields.values()) == set(view.model._meta.fields.values())


async def test_get():
    # 1. success: no statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 2. failed: simple statement and not found
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'name': '1'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    # 3. failed: column not found
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'qqq': 1}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 4. failed: invalid parameter (Invalid operator)
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'qqq.a.b': 1}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    #  5. failed: invalid parameter (bad value)
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt': 'qq'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    #  6. success: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  7. success: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt.eq': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  8. not found: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt.lt': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    #  9. success: simple statement
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'flt.le': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_get_loadfk():
    #  1. success: simple statement
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  2. failed: syntax
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', ':loadfk': {'aaa': None}}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    #  3. failed: column not found
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', ':loadfk': json.dumps({'aaa': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    #  4. success: simple load
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', ':loadfk': json.dumps({'link_id': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['link_id']['id'] == 1
    assert view.ret_val['data']['link_id']['name'] == 'Name1'

    #  5. success: load as
    request = make_mocked_request('GET', '/api/test2', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', ':loadfk': json.dumps({'link_id': {'as': 'link'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['link']['id'] == 1
    assert view.ret_val['data']['link']['name'] == 'Name1'

    # 7. success: recursion load
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', ':loadfk': json.dumps({'link_id': {'loadfk': {'link_id': None}}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['link_id']['id'] == 2
    assert view.ret_val['data']['link_id']['name'] == 'NameB2'
    assert view.ret_val['data']['link_id']['link_id']['id'] == 2
    assert view.ret_val['data']['link_id']['link_id']['name'] == 'Name2'
    assert view.ret_val['data']['link_id']['link_id']['count'] == 2

    # 8. failed: load soft link, wrong table name
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC1', ':loadfk': json.dumps({'id': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 9. failed: load soft link, wrong table name and wrong condition
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'not found', ':loadfk': json.dumps({'id': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 10. failed: foreign key not match table
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', ':loadfk': json.dumps({'id': {'table': 'test1'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 11. success: soft foreign key
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', ':loadfk': json.dumps({'id': {'table': 't2'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id']['id'] == 2
    assert view.ret_val['data']['id']['name'] == 'NameB2'

    # 12. success: soft foreign key as
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', ':loadfk': json.dumps({'id': {'table': 't2', 'as': 't2'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id'] == 2
    assert view.ret_val['data']['t2']['id'] == 2
    assert view.ret_val['data']['t2']['name'] == 'NameB2'

    # 13. success: list values
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', ':loadfk': json.dumps({'id': [{'table': 't2', 'as': 't2'}]})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id'] == 2
    assert view.ret_val['data']['t2']['id'] == 2
    assert view.ret_val['data']['t2']['name'] == 'NameB2'

    # 13. success: read multi tables with one key
    request = make_mocked_request('GET', '/api/test3', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', ':loadfk': json.dumps({'id': [{'table': 't2', 'as': 't2'}, {'table': 't1', 'as': 't1'}]})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id'] == 2
    assert view.ret_val['data']['t2']['id'] == 2
    assert view.ret_val['data']['t2']['name'] == 'NameB2'
    assert view.ret_val['data']['t1']['name'] == 'Name2'


async def test_new():
    # 1. simple insert
    request = make_mocked_request('POST', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    request._post = dict(name='Name6', binary=b'test6', count=1, json={'q': 1, 'w6': 2})
    view = ATestView(app, request)
    await view._prepare()
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'] == 1

    # 2. insert and return records
    request = make_mocked_request('POST', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    request._post = dict(name='Name6', binary=b'test6', count=1, json=json.dumps({'q': 1, 'w6': 2}))
    request._post[':returning'] = True
    view = ATestView(app, request)
    await view._prepare()
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert isinstance(view.ret_val['data'], list)
    assert view.ret_val['data'][0]['name'] == 'Name6'

    # 3. insert without necessary parameter
    request = make_mocked_request('POST', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    request._post = dict(name='Name6',count=1)
    view = ATestView(app, request)
    await view._prepare()
    await view.new()
    assert view.ret_val['code'] == RETCODE.INVALID_POSTDATA


async def test_update():
    a1 = ATestModel.create(name='Name1A', binary=b'test1A', count=1, json={'q': 1, 'w1a': 2})
    a2 = ATestModel.create(name='Name2A', binary=b'test2A', count=2, json={'q': 1, 'w2a': 2})
    a3 = ATestModel.create(name='Name3A', binary=b'test3A', count=3, json={'q': 1, 'w3a': 2})

    # 1. simple update
    request = make_mocked_request('POST', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    request._post = dict(name='Name1AA', count='4')
    view = ATestView(app, request)
    view._params_cache = {'name': 'Name1A'}
    await view._prepare()
    await view.update()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'] == 1

    val = ATestModel.get(ATestModel.binary==b'test1A')
    assert val.name == 'Name1AA'

    # 1. simple update with returning
    request = make_mocked_request('POST', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    request._post = dict(name='Name2AA', count='5')
    request._post[':returning'] = True
    view = ATestView(app, request)
    view._params_cache = {'name': 'Name2A'}
    await view._prepare()
    await view.update()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert isinstance(view.ret_val['data'], list)
    assert view.ret_val['data'][0]['name'] == 'Name2A'


async def test_is():
    # 1. success: .eq null (sqlite)
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'value': 'null'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 2. success: .ne null
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'value.ne': 'null'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    # 3. success: .is null
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'value.is': 'null'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 4. success: .isnot null
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'value.isnot': 'null'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    # 5. success: .is value
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'name.is': 'Name1'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['binary'] == b'test1'

    # 6. success: .isnot value
    request = make_mocked_request('GET', '/api/test1', headers={}, protocol=mock.Mock(), app=app)
    view = ATestView(app, request)
    view._params_cache = {'name.isnot': 'Name1'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['binary'] == b'test2'


if __name__ == '__main__':
    from slim.utils.async import sync_call
    sync_call(test_bind)
    sync_call(test_get)
    sync_call(test_get_loadfk)
    sync_call(test_new)
    sync_call(test_update)
    sync_call(test_is)
