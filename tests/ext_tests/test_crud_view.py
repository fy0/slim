import pytest
from peewee import TextField, Model, SqliteDatabase

from pycurd.crud.ext.peewee_crud import PeeweeCrud
from pycurd.permission import RoleDefine, TablePerm, A
from pycurd.types import RecordMapping
from pycurd.values import ValuesToWrite
from slim import Application
from slim.base.user import BaseUser, BaseUserViewMixin
from slim.ext.crud_view.crud_view import CrudView
from slim.tools.test import invoke_interface

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456')
db = SqliteDatabase(":memory:")


class BaseModel(Model):
    class Meta:
        database = db


class ExampleModel(BaseModel):
    test = TextField()

    class Meta:
        table_name = 'example'


db.create_tables([ExampleModel])


class Example(RecordMapping):
    id: int
    test: str


c = PeeweeCrud({
    None: RoleDefine({
        Example: TablePerm({
            Example.id: {A.READ},
            Example.test: {A.CREATE, A.READ, A.QUERY, A.UPDATE}
        }, allow_delete=True)
    })
}, {
    Example: ExampleModel
}, db)


class SimpleUser(dict, BaseUser):
    pass


class UserViewMixin(BaseUserViewMixin):
    async def get_current_user(self):
        return SimpleUser({'name': 'qiuye'})


@app.route.view('example', 'Example API')
class ExampleView(CrudView, UserViewMixin):
    model = Example
    crud = c


app.prepare()


async def test_create():
    post = {'id': -1, 'test': 'aaa'}
    view = await invoke_interface(app, ExampleView().insert, post=post)
    assert view.response
    assert view.response.data != [-1]


async def test_list():
    ExampleModel.delete().execute()
    ExampleModel.insert_many([('a1',), ('a2',), ('a3',)], ['test']).execute()

    view = await invoke_interface(app, ExampleView().list, {
        'test.eq': 'a2'
    })

    assert view.response
    assert len(view.response.data) == 1
    assert view.response.data[0]['test'] == 'a2'
    ExampleModel.delete().execute()


async def test_update():
    ExampleModel.delete().execute()
    ExampleModel.insert_many([('c1',), ('c2',)], ['test']).execute()

    view = await invoke_interface(app, ExampleView().update, {
        'test.eq': 'c1'
    }, {
        'test': 'c4'
    })

    assert len(view.response.data) == 1
    assert ExampleModel.select().where(ExampleModel.test == 'c4').count() == 1
    ExampleModel.delete().execute()


async def test_delete():
    ExampleModel.delete().execute()
    ExampleModel.insert_many([('b1',), ('b2',), ('b3',)], ['test']).execute()

    view = await invoke_interface(app, ExampleView().delete, {
        'test.eq': 'b2'
    })

    assert view.response
    assert len(view.response.data) == 1
    assert [x for x in ExampleModel.select().where(ExampleModel.test == 'b2')] == []
    ExampleModel.delete().execute()
