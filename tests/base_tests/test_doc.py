import pytest
from slim import Application
from slim.tools.test import invoke_interface, make_mocked_request
from slim.ext.openapi.serve import doc_serve

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)
app.prepare()


async def test_doc_serve():
    doc_serve(app)
    req = make_mocked_request('GET', '/redoc')

    async def send(message):
        if message['type'] == 'http.response.start':
            assert message['status'] == 200

    await app(req.scope, req.receive, send, raise_for_resp=True)
