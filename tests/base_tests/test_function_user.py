from typing import Type

import pytest
from slim import Application
from slim.base._view.request_view import RequestView
from slim.base.user import BaseUser, BaseUserViewMixin
from slim.retcode import RETCODE
from slim.tools.test import invoke_interface

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


class SimpleUser(dict, BaseUser):
    pass


class UserViewMixin(BaseUserViewMixin):
    async def get_current_user(self):
        return SimpleUser({'name': 'qiuye'})


@app.route.get('base')
def for_test(req: RequestView):
    req._.user = req.current_user
    req.finish(RETCODE.SUCCESS)


app.prepare()
app.set_user_mixin_class(UserViewMixin)


async def test_func_with_user():
    view = await invoke_interface(app, for_test)
    assert view.retcode == RETCODE.SUCCESS
    assert view._.user
    assert view._.user['name'] == 'qiuye'
