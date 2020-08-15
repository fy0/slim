import pytest
from slim import Application
from slim.base.view import BaseView
from slim.tools.test import make_asgi_request

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


@app.route.view('base')
class ATestView(BaseView):
    @app.route.interface('GET')
    async def captcha(self):
        pass


async def test_a():
    make_asgi_request
