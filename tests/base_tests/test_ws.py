import json
from typing import Dict

import pytest
from slim import Application
from slim.base.ws import WebSocket
from slim.exception import InvalidRouteUrl
from slim.tools.test import make_mocked_ws_request
from slim.utils import async_call

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None)


@app.route.websocket()
class WS(WebSocket):
    on_connect_ = []
    on_receive_ = []

    async def on_connect(self):
        await super().on_connect()
        for i in self.on_connect_:
            await async_call(i, self)

    async def on_receive(self, data: [str, bytes]):
        for i in self.on_receive_:
            i(self, data)

    async def on_disconnect(self, code):
        await super().on_disconnect(code)


@app.route.websocket()
class WS2(WebSocket):
    pass


@app.route.websocket()
class WSSend(WebSocket):
    async def on_connect(self):
        await super().on_connect()

        await self.send(b'111')
        await self.send('222')
        await self.send_json({'test': [1, 2, 3]})

        await self.send_all('222')
        await self.send_all_json({'test': [1, 2, 3]})


@app.route.websocket('qqq/:test')
class WS3(WebSocket):
    async def on_connect(self):
        await super().on_connect()
        assert self.match_info == {'test': '1'}


app.prepare()


async def test_websocket_base():
    req = await make_mocked_ws_request('/api/ws')
    await app(req.scope, req.receive, req.send)


async def test_websocket_on_connect():
    req = await make_mocked_ws_request('/api/ws')
    flag = 0
    assert len(WS.connections) == 0

    async def func(ws):
        nonlocal flag
        flag = 1
        assert len(ws.connections) == 1
        assert len(WS2.connections) == 0

    WS.on_connect_.append(func)
    await app(req.scope, req.receive, req.send)
    assert flag == 1


async def test_websocket_receive():
    req = await make_mocked_ws_request('/api/ws')

    recv_lst = [
        {'type': 'websocket.connect'},
        {'type': 'websocket.receive', 'text': '111'},
        {'type': 'websocket.receive', 'bytes': b'222'},
        {'type': 'websocket.disconnect', 'code': 1006}
    ]

    async def receive():
        if recv_lst:
            return recv_lst.pop(0)

    def func(ws, data):
        assert data == '111'
        WS.on_receive_.clear()
        WS.on_receive_.append(func2)

    def func2(ws, data):
        assert data == b'222'

    WS.on_receive_.append(func)
    await app(req.scope, receive, req.send)


async def test_websocket_send():
    req = await make_mocked_ws_request('/api/ws_send') # WSSend

    lst = [
        {'type': 'websocket.accept'},
        {'type': 'websocket.send', 'bytes': b'111'},
        {'type': 'websocket.send', 'text': '222'},
        {'type': 'websocket.send', 'text': json.dumps({'test': [1, 2, 3]})},
        {'type': 'websocket.send', 'text': '222'},
        {'type': 'websocket.send', 'text': json.dumps({'test': [1, 2, 3]})},
    ]

    async def send(message):
        assert message == lst.pop(0)

    await app(req.scope, req.receive, send)


async def test_websocket_regex_route():
    req = await make_mocked_ws_request('/api/qqq/1')
    await app(req.scope, req.receive, req.send)


async def test_websocket_failed():
    route_info, call_kwargs_raw = app.route.query_ws_path('/api/asd')
    assert route_info is None
    assert call_kwargs_raw is None
