import json

import pytest
from unittest import mock
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from playhouse.sqlite_ext import JSONField as SQLITE_JSONField
from slim.tools.test import make_mocked_view, invoke_interface, make_mocked_request

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
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
        table_name = 'test'
        database = db


class ATestBModel(Model):
    name = TextField()
    link = ForeignKeyField(ATestModel)

    class Meta:
        table_name = 'test2'
        database = db


class ATestCModel(Model):
    name = TextField()
    link = ForeignKeyField(ATestBModel)

    class Meta:
        table_name = 'test3'
        database = db


class ATestDModel(Model):
    name = TextField()
    link = ForeignKeyField(ATestBModel, null=True)

    class Meta:
        table_name = 'test4'
        database = db


class ATestNewModel(Model):
    name = TextField(default='aaa')

    class Meta:
        table_name = 'test_new'
        database = db


db.create_tables([ATestModel, ATestBModel, ATestCModel, ATestDModel, ATestNewModel])
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

ATestDModel.insert_many([
    {'name': 'NameD1', 'link': None},
    {'name': 'NameD2', 'link': None},
    {'name': 'NameD3', 'link': None},
])


@app.route.view('test1')
class ATestView(PeeweeView):
    model = ATestModel


@app.route.view('test2')
class ATestView2(PeeweeView):
    model = ATestBModel


@app.route.view('test3')
class ATestView3(PeeweeView):
    model = ATestCModel

    @classmethod
    def ready(cls):
        cls.add_soft_foreign_key('id', 'wrong table name')
        cls.add_soft_foreign_key('id', 'test2', 't2')
        cls.add_soft_foreign_key('id', 'test', 't1')


@app.route.view('test4')
class ATestView4(PeeweeView):
    model = ATestDModel

    @classmethod
    def ready(cls):
        cls.add_soft_foreign_key('id', 'test')


@app.route.view('test_new')
class ATestNewView(PeeweeView):
    model = ATestNewModel


async def test_bind():
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    assert len(view.model._meta.fields) == len(view.fields)
    assert set(view.model._meta.fields.values()) == set(view.model._meta.fields.values())


async def test_get_without_stmt():
    # 1. success: no statement
    view: PeeweeView = await make_mocked_view(app, ATestView, 'GET', '/api/test1')
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_get_with_simple_stmt_failed():
    # 2. failed: simple statement and not found
    params = {'name': '1'}
    view: PeeweeView = await make_mocked_view(app, ATestView, 'GET', '/api/test1', params=params)
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    # 3. failed: column not found
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    view._params_cache = {'qqq': 1}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 4. failed: invalid parameter (Invalid operator)
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    view._params_cache = {'qqq.a.b': 1}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    #  5. failed: invalid parameter (bad value)
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    view._params_cache = {'flt': 'qq'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    #  6. success: simple statement
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    view._params_cache = {'flt': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  7. success: simple statement
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    view._params_cache = {'flt.eq': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  8. not found: simple statement
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    view._params_cache = {'flt.lt': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    #  9. success: simple statement
    request = make_mocked_request('GET', '/api/test1')
    view = ATestView(app, request)
    view._params_cache = {'flt.le': '0'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_get_loadfk():
    #  1. success: simple statement
    request = make_mocked_request('GET', '/api/test2')
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1'}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    #  2. invalid params: loadfk must be json string
    view = await make_mocked_view(app, ATestView2, 'GET', '/api/test2', {'name': 'NameB1', 'loadfk': {'aaa': None}})
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    #  3. failed: column not found
    request = make_mocked_request('GET', '/api/test2')
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', 'loadfk': json.dumps({'aaa': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    #  4. success: simple load
    request = make_mocked_request('GET', '/api/test2')
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', 'loadfk': json.dumps({'link_id': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['link_id']['id'] == 1
    assert view.ret_val['data']['link_id']['name'] == 'Name1'

    #  5. success: load as
    request = make_mocked_request('GET', '/api/test2')
    view = ATestView2(app, request)
    view._params_cache = {'name': 'NameB1', 'loadfk': json.dumps({'link_id': {'as': 'link'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['link']['id'] == 1
    assert view.ret_val['data']['link']['name'] == 'Name1'

    # 7. success: recursion load
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', 'loadfk': json.dumps({'link_id': {'loadfk': {'link_id': None}}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['link_id']['id'] == 2
    assert view.ret_val['data']['link_id']['name'] == 'NameB2'
    assert view.ret_val['data']['link_id']['link_id']['id'] == 2
    assert view.ret_val['data']['link_id']['link_id']['name'] == 'Name2'
    assert view.ret_val['data']['link_id']['link_id']['count'] == 2

    # 8. failed: load soft link, wrong table name
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC1', 'loadfk': json.dumps({'id': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 9. failed: load soft link, wrong table name and wrong condition
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'not found', 'loadfk': json.dumps({'id': None})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 10. failed: foreign key not match table
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', 'loadfk': json.dumps({'id': {'table': 'test1'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED

    # 11. success: soft foreign key
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', 'loadfk': json.dumps({'id': {'table': 't2'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id']['id'] == 2
    assert view.ret_val['data']['id']['name'] == 'NameB2'

    # 12. success: soft foreign key as
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', 'loadfk': json.dumps({'id': {'table': 't2', 'as': 't2'}})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id'] == 2
    assert view.ret_val['data']['t2']['id'] == 2
    assert view.ret_val['data']['t2']['name'] == 'NameB2'

    # 13. success: list values
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', 'loadfk': json.dumps({'id': [{'table': 't2', 'as': 't2'}]})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id'] == 2
    assert view.ret_val['data']['t2']['id'] == 2
    assert view.ret_val['data']['t2']['name'] == 'NameB2'

    # 13. success: read multi tables with one key
    request = make_mocked_request('GET', '/api/test3')
    view = ATestView3(app, request)
    view._params_cache = {'name': 'NameC2', 'loadfk': json.dumps({'id': [{'table': 't2', 'as': 't2'}, {'table': 't1', 'as': 't1'}]})}
    await view._prepare()
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['id'] == 2
    assert view.ret_val['data']['t2']['id'] == 2
    assert view.ret_val['data']['t2']['name'] == 'NameB2'
    assert view.ret_val['data']['t1']['name'] == 'Name2'

    # 14. loadfk and all foreign keys are null
    request = make_mocked_request('GET', '/api/test4/list/1')
    view = ATestView4(app, request)
    view._params_cache = {'loadfk': json.dumps({'link_id': None})}
    await view._prepare()
    await view.list()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert len(view.ret_val['data']['items']) == 0

    # 15. loadfk and all foreign keys are null
    view = await make_mocked_view(app, ATestView4, 'GET', '/api/test4/list/1',
                                           {'loadfk': json.dumps({'link_id': None})})
    await view.list()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert len(view.ret_val['data']['items']) == 0


async def test_new_simple():
    # 1. simple insert
    post = dict(name='Name6', binary=b'test6', count=1, json={'q': 1, 'w6': 2})
    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/test1', post=post)

    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'] == 1


async def test_new_simple_with_return():
    # 2. insert and return records
    post = dict(name='Name6', binary=b'test6', count=1, json={'q': 1, 'w6': 2}, returning=True)
    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/test1', post=post)

    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['name'] == 'Name6'


async def test_new_failed():
    # 3. insert without necessary parameter
    post = dict(name='Name6', count=1)
    view: PeeweeView = await make_mocked_view(app, ATestView, 'POST', '/api/test1', post=post)
    await view.new()
    assert view.ret_val['code'] == RETCODE.INVALID_POSTDATA


async def test_new_without_data():
    assert ATestNewModel.create()
    view: PeeweeView = await make_mocked_view(app, ATestNewView, 'POST', '/api/test_new', post={})
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_set():
    a1 = ATestModel.create(name='Name1A', binary=b'test1A', count=1, json={'q': 1, 'w1a': 2})
    a2 = ATestModel.create(name='Name2A', binary=b'test2A', count=2, json={'q': 1, 'w2a': 2})
    a3 = ATestModel.create(name='Name3A', binary=b'test3A', count=3, json={'q': 1, 'w3a': 2})

    # 1. simple update
    params = {'name': 'Name1A'}
    post = dict(name='Name1AA', count='4')
    view = await invoke_interface(app, ATestView().set, params=params, post=post)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'] == 1

    val = ATestModel.get(ATestModel.binary == b'test1A')
    assert val.name == 'Name1AA'

    # 2. simple update with returning
    params = {'name': 'Name2A'}
    post = dict(name='Name2AA', count='5', returning=True)
    view = await invoke_interface(app, ATestView().set, params=params, post=post)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'][0]['name'] == 'Name2AA'

    # 3. incr
    params = {'name': 'Name3A'}
    post = {'count.incr': 1, 'returning': True}
    view = await invoke_interface(app, ATestView().set, params=params, post=post)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'][0]['name'] == 'Name3A'
    assert view.ret_val['data'][0]['count'] == 4

    # 3. incr -1
    params = {'name': 'Name3A'}
    post = {'count.incr': -2, 'returning': True}
    view = await invoke_interface(app, ATestView().set, params=params, post=post)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'][0]['name'] == 'Name3A'
    assert view.ret_val['data'][0]['count'] == 2


async def test_is():
    # 1. success: .eq null (sqlite)
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', {'value': 'null'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 2. success: .ne null
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', {'value.ne': 'null'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    # 3. success: .is null
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', {'value.is': 'null'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 4. success: .isnot null
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', {'value.isnot': 'null'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.NOT_FOUND

    # 5. success: .is value
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', {'name.is': 'Name1'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['binary'] == b'test1'

    # 6. success: .isnot value
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', {'name.isnot': 'Name1'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['binary'] == b'test2'


async def test_delete():
    assert ATestModel.select().where(ATestModel.name=='Name1B').count() == 0
    b1 = ATestModel.create(name='Name1B', binary=b'test1B', count=1, json={'q': 1, 'w1b': 2})
    # b2 = ATestModel.create(name='Name2B', binary=b'test2B', count=2, json={'q': 1, 'w2b': 2})
    # b3 = ATestModel.create(name='Name3B', binary=b'test3B', count=3, json={'q': 1, 'w3b': 2})
    assert ATestModel.select().where(ATestModel.name=='Name1B').count() == 1

    view = await make_mocked_view(app, ATestView, 'POST', '/api/test4', {'name': 'Name1B'})
    await view.delete()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert ATestModel.select().where(ATestModel.name=='Name1B').count() == 0


async def test_select_exclude():
    params = {
        'select': 'name,binary,count,active,flt,json,value',
        '-select': 'binary'
    }
    view = await invoke_interface(app, ATestView().get, params)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'].keys() == {'name', 'count', 'active', 'flt', 'json', 'value'}


async def test_select_exclude2():
    params = {
        '-select': 'binary'
    }
    view = await invoke_interface(app, ATestView().get, params)
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'].keys() == {'id', 'name', 'count', 'active', 'flt', 'json', 'value'}


async def test_select():
    # 1. success
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1',
                                           {'select': 'name,binary,count,active,flt,json,value'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'].keys() == {'name', 'binary', 'count', 'active', 'flt', 'json', 'value'}

    # 2. success: list
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1',
                                           {'select': 'name,binary,count,active,flt,json,value'})
    await view.list()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 3. success: random spaces
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1',
                                           {'select': 'name, binary,count,\n active,flt,\rjson,\t value'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 4. success: random spaces
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1',
                                           {'select': 'name'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'].keys() == {'name'}

    # 5. failed: Column not found
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1', {'select': 'name1,binary'})
    await view.get()
    assert view.ret_val['code'] == RETCODE.FAILED


async def test_value_type():
    # 1. success
    post = {'name': 'Name1BB', 'binary': b'test1bb', 'json': {'q': 1, 'w6': 2}, 'count': 4}
    view = await make_mocked_view(app, ATestView, 'POST', '/api/test1', post=post)
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data'] == 1

    val = ATestModel.get(ATestModel.binary == b'test1bb')
    assert val.name == 'Name1BB'

    # 2. failed: post, bad json
    view = await make_mocked_view(app, ATestView, 'POST', '/api/test1',
                                           post={'name': 'Name2BB', 'binary': b'test2bb',
                                                 'json': '{', 'count': 5})
    await view.new()
    assert view.ret_val['code'] == RETCODE.SUCCESS

    # 2. failed: params, bad json
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1',
                                           params={'json': '{', 'count': 5})
    await view.get()
    assert view.ret_val['code'] == RETCODE.SUCCESS


async def test_in():
    # 1. invalid params: not a json string
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1',
                                           params={'name.in': ['Name1', 'Name2', 'Name3']})
    await view.get()
    assert view.ret_val['code'] == RETCODE.INVALID_PARAMS

    # 2. success
    view = await make_mocked_view(app, ATestView, 'GET', '/api/test1',
                                           params={'name.in': json.dumps(['Name1', 'Name2', 'Name3'])})
    await view.list()
    assert view.ret_val['code'] == RETCODE.SUCCESS
    assert view.ret_val['data']['info']['items_count'] == 3


class ATestReadyModel(ATestModel):
    class Meta:
        table_name = 'ready_test'


class ATestReadyModel2(ATestModel):
    class Meta:
        table_name = 'ready_test2'


@app.route.view('test1')
class ATestReadyView(PeeweeView):
    model = ATestReadyModel
    a = 1

    @classmethod
    def ready(cls):
        cls.a = 2


@app.route.view('test1')
class ATestReadyView2(PeeweeView):
    model = ATestReadyModel2
    a = 1

    @classmethod
    async def ready(cls):
        cls.a = 2


async def test_ready():
    assert ATestReadyView.a == 2
    assert ATestReadyView2.a == 2


app.prepare()
