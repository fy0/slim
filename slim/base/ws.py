import json
import logging
import aiohttp
import asyncio
from aiohttp import web
from aiohttp.web_request import BaseRequest
from slim.base.user import BaseUserMixin
from slim.retcode import RETCODE
from ..utils import MetaClassForInit, async_call

logger = logging.getLogger(__name__)


class WSRouter(BaseUserMixin, metaclass=MetaClassForInit):
    heartbeat_timeout = 30
    connections = set()
    _on_message = {}

    def __init__(self):
        self.access_token = None

    def setup_user_key(self, key, expires=30):
        self.access_token = key

    def teardown_user_key(self):
        self.access_token = None

    def get_current_user(self):
        if self.access_token is not None:
            return self.get_user_by_key(self.access_token)

    @classmethod
    def cls_init(cls):
        cls.connections = set()
        if len(cls._on_message) > 0:
            cls._on_message = cls._on_message.copy()
        else:
            cls._on_message = {}

    @classmethod
    def route(cls, command):
        def _(obj):
            cls._on_message.setdefault(command, [])
            cls._on_message[command].append(obj)
        return _

    async def on_close(self, ws):
        pass

    async def _handle(self, request: BaseRequest):
        ws = web.WebSocketResponse(receive_timeout=self.heartbeat_timeout)
        await ws.prepare(request)
        ws.request = request
        self.connections.add(ws)
        wsid = ws.headers['Sec-Websocket-Accept']
        logger.debug('websocket connected: %r, %d client(s) online' % (wsid, len(self.connections)))
        self.ws = ws

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == 'ws.close':
                        await ws.close()
                    elif msg.data == 'ws.ping':
                        await ws.send_str('ws.pong')
                    else:
                        try:
                            # request id, command, data
                            rid, command, data = json.loads(msg.data)
                        except json.decoder.JSONDecodeError:
                            logger.error('websocket command parse failed %s: %r' % (msg.data, wsid))
                            continue

                        def send_json_wrap(rid):
                            async def send_json(code, data=NotImplemented):
                                if data is NotImplemented:
                                    data = RETCODE.txt_cn.get(code)
                                val = {'code': code, 'data': data}
                                logger.info('websocket reply %r - %s: %r' % (command, val, wsid))
                                await ws.send_json([rid, val])

                            return send_json

                        send_json = send_json_wrap(rid)

                        if command in self._on_message:
                            logger.info('websocket command %r - %s: %r' % (command, data, wsid))
                            for i in self._on_message[command]:
                                ret = await async_call(i, self, send_json, data)
                                '''
                             def ws_command_test(wsr: WSRouter, send_json, data):
                                pass
                             '''
                                if ret is not None:
                                    await send_json(*ret)
                        else:
                            logger.info('websocket command not found %s: %r' % (command, wsid))

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.debug('websocket connection closed with exception %s: %r' % (ws.exception(), wsid))
                    break
        except (asyncio.TimeoutError, asyncio.CancelledError) as e:
            # timeout, ws.close_code == 1006
            pass

        self.connections.remove(ws)
        await self.on_close(ws)
        if ws.close_code == 1006:
            logger.debug('websocket connection timeout closed: %r, %d client(s) online' % (wsid, len(self.connections)))
        else:
            logger.debug('websocket connection closed: %r, %d client(s) online' % (wsid, len(self.connections)))
        return ws


@WSRouter.route('hello')
def ws_command_signin(wsr: WSRouter, send_json, data):
    send_json(RETCODE.SUCCESS, 'Hello Websocket!')
    return RETCODE.SUCCESS, 'Hello Again!'


@WSRouter.route('signin')
def ws_command_signin(wsr: WSRouter, send_json, data):
    wsr.setup_user_key(data['access_token'])
    return RETCODE.SUCCESS


@WSRouter.route('signout')
def ws_command_signin(wsr: WSRouter, send_json, data):
    wsr.teardown_user_key()
    return RETCODE.SUCCESS
