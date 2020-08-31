from typing import Dict

import pytest
from slim import Application
from slim.base.types.asgi import WSRespond
from slim.base.ws import WebSocket
from slim.tools.test import invoke_interface, make_mocked_request, make_mocked_ws_request

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


@app.route.websocket()
class WS(WebSocket):
    on_connect_ = []

    def __init__(self, app: 'Application', request: 'ASGIRequest', url_info: Dict):
        super().__init__(app, request, url_info)

    async def on_connect(self):
        for i in self.on_connect_:
            i(self)

    async def on_receive(self, text: str, bytes_: bytes, respond: WSRespond):
        pass

    def on_disconnect(self, code):
        pass


app.prepare()


async def test_websocket_base():
    req = await make_mocked_ws_request('/api/ws')
    await app(req.scope, req.receive, req.send)


async def test_websocket_on_connect():
    req = await make_mocked_ws_request('/api/ws')
    flag = 0

    def func(ws):
        nonlocal flag
        flag = 1

    WS.on_connect_.append(func)
    await app(req.scope, req.receive, req.send)
    assert flag == 1
