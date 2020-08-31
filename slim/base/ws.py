import json
import logging
from abc import abstractmethod
import asyncio

import typing
from collections import Counter
from typing import Set

from multidict import CIMultiDict

from ._view.base_view import HTTPMixin
from .types.asgi import Scope, Receive, Send, WSRespond
from .user import BaseUserViewMixin, BaseUser
from ..retcode import RETCODE
from ..utils import MetaClassForInit, async_call

if typing.TYPE_CHECKING:
    from .web import ASGIRequest, Application

logger = logging.getLogger(__name__)


class WebSocket(HTTPMixin):
    """
    Websocket handler based on asgi document:
    https://asgi.readthedocs.io/en/latest/specs/www.html#websocket
    """
    connections: Set['WebSocket']

    def __init_subclass__(cls, **kwargs):
        cls.connections = set()

    def __init__(self, app: 'Application', request: 'ASGIRequest', url_info: typing.Dict):
        super().__init__(app)
        self.url_info = url_info

    @property
    def headers(self) -> CIMultiDict:
        """
        Get headers
        """
        return self.request.headers

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
                # throw abort exception to stop connect
                await async_call(self.on_connect)
                await send({'type': 'websocket.accept'})

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

    @abstractmethod
    async def on_receive(self, data: [str, bytes]):
        pass

    async def on_disconnect(self, code: int):
        self.connections.remove(self)


class WSCommand(WebSocket):
    """
    Router is only one, ws objects are many.
    """
    users: Set['WSCommand']
    heartbeat_timeout = 30
    _on_message = {}

    def __init_subclass__(cls, **kwargs):
        cls.users = set()
        cls._on_message = cls._on_message.copy()

    @classmethod
    def route(cls, command):
        def _(obj):
            cls._on_message.setdefault(command, [])
            cls._on_message[command].append(obj)
        return _

    async def on_receive(self, data: [str, bytes]):
        wsid = id(self)

        try:
            # request id, command, data
            rid, command, data = json.loads(data)
        except json.decoder.JSONDecodeError:
            logger.error('WS command parse failed %s: %r' % (data, wsid))
            return

        def make_send_json(rid):
            async def _send_json(data):
                logger.info('WS reply %r - %s: %r' % (command, data, wsid))
                await self.send_json([rid, data])

            return _send_json

        send = make_send_json(rid)

        if command in self._on_message:
            logger.info('WS command %r - %s: %r' % (command, data, wsid))
            for func in self._on_message[command]:
                ret = await async_call(func, self, data)
                '''
                 def ws_command_test(ws: WebSocket, data):
                    pass
                 '''

                await send({
                    'code': RETCODE.SUCCESS,
                    'data': ret
                })
        else:
            logger.info('WS command not found %s: %r' % (command, wsid))

    async def on_connect(self):
        await super().on_connect()
        user = self.current_user
        if user:
            logger.debug('WS user signin: %s' % user)
            self.users.add(self)
        logger.debug('WS connected: %r, %d client(s) online' % (id(self), len(self.connections)))

    async def on_disconnect(self, code: int):
        await super().on_disconnect(code)

        if self in self.users:
            self.users.remove(self)
            logger.debug('WS user signout: %s' % self.current_user)

        if code == 1006:
            logger.debug('WS conn timeout closed: %r, %d client(s) online' % (id(self), len(self.connections)))
        else:
            logger.debug('WS conn closed: %r, %d client(s) online' % (id(self), len(self.connections)))

        # error
        # logger.debug('WS conn closed with exception %s: %r' % (ws.exception(), wsid))


'''
def _show_online(wsr):
    logger.debug('WS count: %d visitors(include %s users), %d clients online' % (
        len(wsr.count), len(wsr.users), len(wsr.connections)))

'''
