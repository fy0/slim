import pytest
from slim import Application
from slim.base._view.request_view import RequestView
from slim.retcode import RETCODE
from slim.tools.test import invoke_interface

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


@app.route.get('base')
def for_test(request: RequestView):
    request.finish(RETCODE.SUCCESS, 111)


app.prepare()


async def test_func_base():
    view = await invoke_interface(app, for_test)
    assert view.retcode == RETCODE.SUCCESS
