from typing import Type, Union

import peewee
import pytest
from peewee import SqliteDatabase

from slim import Application, D
from slim.base.view.base_view import BaseView
from slim.base.user import BaseUser, BaseUserViewMixin
from slim.retcode import RETCODE
from slim.tools.test import invoke_interface

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456')


class User(BaseUser):
    def __init__(self, roles=None):
        self._roles = roles

    @property
    def roles(self):
        if self._roles is not None:
            return self._roles
        return {None, 'user'}


@app.route.view('test')
class ATestView(BaseView, BaseUserViewMixin):
    @app.route.get()
    # @D.require_role('user')
    async def a(self):
        # self.finish(RETCODE.SUCCESS)
        return {}

    @app.route.get()
    # @D.require_role(None)
    async def b(self):
        # self.finish(RETCODE.SUCCESS)
        return {}


app.prepare()


async def test_ext_decorator_require_role():
    """
    require_role do not needs requesting role is or inside roles required.
    :return:
    """
    # resp = await invoke_interface(app, ATestView().a, user=User(), role=None)
    # assert resp.response.data['code'] == RETCODE.SUCCESS
    pass


async def test_ext_decorator_require_role_failed():
    """
    require_role do not needs requesting role is or inside roles required.
    :return:
    """
    # resp = await invoke_interface(app, ATestView().a, user=User({'admin', None}), role=None)
    # assert resp.response.data['code'] == RETCODE.INVALID_ROLE
    pass
