import json
import logging
from abc import abstractmethod
import aiohttp
import asyncio
from aiohttp import web
from aiohttp.web_request import BaseRequest
from .user import BaseUserViewMixin, BaseUser
from ..retcode import RETCODE
from ..utils.count_dict import CountDict
from ..utils import MetaClassForInit, async_call

logger = logging.getLogger(__name__)


class WSRouter(metaclass=MetaClassForInit):
    """
    Router is only one, ws objects are many.
    """
    heartbeat_timeout = 30
    _on_message = {}

    connections = set()
    users = CountDict()
    count = CountDict()

    @abstractmethod
    def get_user_by_key(self, key):
        pass

    @classmethod
    def cls_init(cls):
        cls.connections = set()
        cls.users = CountDict()
        cls.count = CountDict()

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
        ws.access_token = None
        self.connections.add(ws)
        wsid = ws.headers['Sec-Websocket-Accept']
        logger.debug('WS connected: %r, %d client(s) online' % (wsid, len(self.connections)))

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
                            logger.error('WS command parse failed %s: %r' % (msg.data, wsid))
                            continue

                        def make_send_json(rid):
                            async def _send_json(data):
                                logger.info('WS reply %r - %s: %r' % (command, data, wsid))
                                await ws.send_json([rid, data])
                            return _send_json
                        send = make_send_json(rid)

                        if command in self._on_message:
                            logger.info('WS command %r - %s: %r' % (command, data, wsid))
                            for i in self._on_message[command]:
                                ret = await async_call(i, self, ws, send, data)
                                '''
                             def ws_command_test(wsr: WSRouter, ws, send, data):
                                pass
                             '''
                                await send({
                                    'code': RETCODE.WS_DONE,
                                    'data': ret
                                })
                        else:
                            logger.info('WS command not found %s: %r' % (command, wsid))

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.debug('WS conn closed with exception %s: %r' % (ws.exception(), wsid))
                    break
        except (asyncio.TimeoutError, asyncio.CancelledError) as e:
            # timeout, ws.close_code == 1006
            pass

        self.connections.remove(ws)
        await self.on_close(ws)
        if ws.close_code == 1006:
            logger.debug('WS conn timeout closed: %r, %d client(s) online' % (wsid, len(self.connections)))
        else:
            logger.debug('WS conn closed: %r, %d client(s) online' % (wsid, len(self.connections)))
        return ws


@WSRouter.route('hello')
async def ws_command_signin(wsr: WSRouter, ws, send, data):
    await send('Hello Websocket!')
    return 'Hello Again!'


def _show_online(wsr):
    logger.debug('WS count: %d visitors(include %s users), %d clients online' % (
        len(wsr.count), len(wsr.users), len(wsr.connections)))


@WSRouter.route('count')
async def ws_command_signin(wsr: WSRouter, ws, send, key):
    wsr.count[key].add(ws)
    _show_online(wsr)


@WSRouter.route('signin')
async def ws_command_signin(wsr: WSRouter, ws, send, data):
    if 'access_token' in data:
        user = wsr.get_user_by_key(data['access_token'])
        if user:
            wsr.users[user].add(ws)
            ws.access_token = data['access_token']
            logger.debug('WS user signin: %s' % user)
            _show_online(wsr)
    return RETCODE.SUCCESS


@WSRouter.route('signout')
async def ws_command_signout(wsr: WSRouter, ws, send, data):
    if ws.access_token:
        user = wsr.get_user_by_key(ws.access_token)
        del wsr.users[user]
        logger.debug('WS user signout: %s' % user)
