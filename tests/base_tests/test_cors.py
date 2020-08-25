import pytest
from slim import Application
from slim.base._view.request_view import RequestView
from slim.retcode import RETCODE
from slim.tools.test import invoke_interface, make_mocked_request

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


@app.route.get('base')
def for_test(request: RequestView):
    request.finish(RETCODE.SUCCESS, 111)


app.prepare()


async def test_cors_options():
    req = make_mocked_request('OPTIONS', '/api/for_test')

    async def send(message):
        if message['type'] == 'http.response.start':
            assert message['status'] != 404

    await app(req.scope, req.receive, send, raise_for_resp=True)
