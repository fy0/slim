import json
import logging
from abc import abstractmethod
import asyncio

import typing
from typing import Set

from .http_mixin import HTTPMixin
from slim.base.types.asgi import Scope, Receive, Send
from slim.utils import async_call

if typing.TYPE_CHECKING:
    from .handle_request import Application
    from .request import ASGIRequest

logger = logging.getLogger(__name__)


class WebSocket(HTTPMixin):
    """
    Websocket handler based on asgi document:
    https://asgi.readthedocs.io/en/latest/specs/www.html#websocket
    """
    connections: Set['WebSocket']

    def __init_subclass__(cls, **kwargs):
        cls.connections = set()

    def __init__(self, app: 'Application', request: 'ASGIRequest', match_info: typing.Dict):
        super().__init__(app, request)
        self.match_info = match_info

    async def send(self, data: [str, bytes]):
        payload = {
            'type': 'websocket.send',
        }
        if isinstance(data, bytes):
            payload['bytes'] = data
        elif isinstance(data, str):
            payload['text'] = data
        await self.request.send(payload)

    async def send_json(self, data):
        return await self.send(json.dumps(data))

    @classmethod
    async def send_all(cls, data: [str, bytes]):
        lst = []
        for i in cls.connections:
            lst.append(i.send(data))
        return await asyncio.gather(*lst)

    @classmethod
    async def send_all_json(cls, data):
        return await cls.send_all(json.dumps(data))

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        while True:
            message = await receive()
            if message['type'] == 'websocket.connect':
                # {'type': 'websocket.connect'}
                await send({'type': 'websocket.accept'})
                await async_call(self.on_connect)

            elif message['type'] == 'websocket.receive':
                # {'type': 'websocket.receive', 'text': '111'}
                m = message.get('text', None)
                if m is None:
                    m = message.get('bytes', None)
                await self.on_receive(m)

            elif message['type'] == 'websocket.disconnect':
                # {'type': 'websocket.disconnect', 'code': 1005}  # 1001  # 1006 timeout
                await async_call(self.on_disconnect, message['code'])
                break

    async def on_connect(self):
        self.connections.add(self)
        logger.debug('WS connected: %r, %d client(s) online' % (id(self), len(self.connections)))

    @abstractmethod
    async def on_receive(self, data: [str, bytes]):
        pass

    async def on_disconnect(self, code: int):
        self.connections.remove(self)

        if code == 1006:
            logger.debug('WS conn timeout closed: %r, %d client(s) online' % (id(self), len(self.connections)))
        else:
            logger.debug('WS conn closed: %r, %d client(s) online' % (id(self), len(self.connections)))
