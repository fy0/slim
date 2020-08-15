from typing import Union, Type

import pytest
from slim.base.user import BaseUserViewMixin, BaseUser
from slim.exception import NoUserViewMixinException
from slim.retcode import RETCODE
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from slim.tools.test import make_mocked_view

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    info = BlobField()

    class Meta:
        table_name = 'test'
        database = db


@app.route.view('test')
class ATestView(PeeweeView):
    model = ATestModel


@app.route.view('test')
class ATestView2(PeeweeView, BaseUserViewMixin):
    model = ATestModel


db.create_tables([ATestModel])


async def test_no_user_view_mixin():
    view = await make_mocked_view(app, ATestView, 'POST', '/api/test')
    assert view.can_get_user is False

    try:
        print(view.current_user)
    except Exception as e:
        assert isinstance(e, NoUserViewMixinException)

    try:
        print(view.roles)
    except Exception as e:
        assert isinstance(e, NoUserViewMixinException)


async def test_user_view_mixin():
    view = await make_mocked_view(app, ATestView2, 'POST', '/api/test')

    assert view.can_get_user
    assert view.roles == {None}
    assert view.current_user is None


class SimpleUser(dict, BaseUser):
    pass


class SyncUserViewMixin(BaseUserViewMixin):
    def get_user_by_key(self, key): pass

    def setup_user_key(self, key, expires=30): pass

    def teardown_user_key(self): pass

    def get_current_user(self):
        return SimpleUser({'name': 'icarus'})


class AsyncUserViewMixin(BaseUserViewMixin):
    def get_user_by_key(self, key): pass

    def setup_user_key(self, key, expires=30): pass

    def teardown_user_key(self): pass

    async def get_current_user(self):
        return SimpleUser({'name': 'icarus'})


class InvalidTokenUserViewMixin(BaseUserViewMixin):
    def get_user_by_token(self: Union['BaseUserViewMixin', 'BaseView'], token) -> Type[BaseUser]:
        if token == '123':
            return SimpleUser({'name': 'icarus'})


@app.route.view('test')
class BTestView(PeeweeView, SyncUserViewMixin):
    model = ATestModel


@app.route.view('test')
class BTestView2(PeeweeView, AsyncUserViewMixin):
    model = ATestModel


@app.route.view('test')
class InvalidTokenUserViewMixin(PeeweeView, InvalidTokenUserViewMixin):
    model = ATestModel


async def test_invalid_token():
    # TODO: still not work
    # view = await make_mocked_view(app, InvalidTokenUserViewMixin, 'POST', '/api/test')
    # assert view.current_user == {'name': 'icarus'}
    pass


async def test_get_current_user():
    # 同步情况下获取当前用户
    view = await make_mocked_view(app, BTestView, 'POST', '/api/test')
    assert view.current_user == {'name': 'icarus'}

    # 异步情况获取当前用户
    view = await make_mocked_view(app, BTestView2, 'POST', '/api/test')
    assert view.current_user == {'name': 'icarus'}
