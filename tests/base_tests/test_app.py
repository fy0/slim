import pytest
from slim import Application
from slim.base._view.request_view import RequestView
from slim.retcode import RETCODE
from slim.tools.test import invoke_interface, make_mocked_request

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


@app.route.get('simple_request')
def simple_request(request: RequestView):
    request.finish(RETCODE.SUCCESS, 'OK')


app.prepare()


async def test_app_life_span():
    recv_data = [
        {'type': 'lifespan.startup'},
        {'type': 'lifespan.shutdown'}
    ]

    async def receive():
        return recv_data.pop(0)

    send_data = [
        'lifespan.startup.complete',
        'lifespan.shutdown.complete'
    ]

    async def send(message):
        assert message['type'] == send_data.pop(0)

    await app({'type': 'lifespan'}, receive, send)


async def test_app_startup_failed():
    recv_data = [
        {'type': 'lifespan.startup'},
        {'type': 'lifespan.shutdown'}
    ]

    async def receive():
        return recv_data.pop(0)

    def on_startup():
        raise Exception('test exception for test_app_startup_failed')

    app.on_startup.append(on_startup)

    send_data = [
        'lifespan.startup.failed',
        'lifespan.shutdown.complete'
    ]

    async def send(message):
        assert message['type'] == send_data.pop(0)

    await app({'type': 'lifespan'}, receive, send, raise_for_resp=True)


async def test_app_handle_request():
    req = make_mocked_request('GET', '/api/simple_request')

    async def send(message):
        assert message == {'type': 'http.response.start', 'status': 200, 'headers': [[b'Content-Type', b'application/json']]} or \
            message == {'type': 'http.response.body', 'body': b'{"code": 0, "data": "OK"}'}

    await app(req.scope, req.receive, send, raise_for_resp=True)
