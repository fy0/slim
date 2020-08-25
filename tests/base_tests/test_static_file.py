import os
import pytest
from slim import Application
from slim.tools.test import make_mocked_request

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)
static_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '_static'))
app.route.add_static('/assets/:file', static_path)
app.route.add_static('/assets2', static_path)
app.prepare()


async def test_static_file():
    req = make_mocked_request('GET', '/assets/1.txt')

    async def send(message):
        if message['type'] == 'http.response.body':
            assert message['body'] == b'111222333'

    await app(req.scope, req.receive, send, raise_for_resp=True)


async def test_static_file_in_dir():
    req = make_mocked_request('GET', '/assets2/bucket/2.txt')

    async def send(message):
        if message['type'] == 'http.response.body':
            assert message['body'] == b'445566'

    await app(req.scope, req.receive, send, raise_for_resp=True)


async def test_static2_file():
    req = make_mocked_request('GET', '/assets2/1.txt')

    async def send(message):
        if message['type'] == 'http.response.body':
            assert message['body'] == b'111222333'

    await app(req.scope, req.receive, send, raise_for_resp=True)


async def test_static_file_failed():
    req = make_mocked_request('GET', '/assets/1.txt')

    async def send(message):
        if message['type'] == 'http.response.body':
            assert message['body'] != b'aabbcc'

    await app(req.scope, req.receive, send, raise_for_resp=True)


async def test_static_file_404():
    req = make_mocked_request('GET', '/assets/2.txt')

    async def send(message):
        if message['type'] == 'http.response.start':
            assert message['status'] == 404

    await app(req.scope, req.receive, send, raise_for_resp=True)


async def test_static_file_404_2():
    req = make_mocked_request('GET', '/assets/bucket')

    async def send(message):
        if message['type'] == 'http.response.start':
            assert message['status'] == 404

    await app(req.scope, req.receive, send, raise_for_resp=True)


async def test_static_file_rel_path():
    req = make_mocked_request('GET', '/assets2/../assets/1.txt')

    async def send(message):
        if message['type'] == 'http.response.start':
            assert message['status'] == 404

    await app(req.scope, req.receive, send, raise_for_resp=True)
