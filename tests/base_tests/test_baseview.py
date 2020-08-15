import pytest
from slim import Application
from slim.base.view import BaseView

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


@app.route.view('base')
class ATestView(BaseView):
    @app.route.interface('GET')
    async def captcha(self):
        pass


async def test_a():
    pass
