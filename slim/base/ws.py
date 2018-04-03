import json
import logging
from asyncio import CancelledError

import aiohttp
import asyncio
from aiohttp import web
from aiohttp.web_request import BaseRequest
from async_timeout import timeout

from slim.retcode import RETCODE
from ..utils import MetaClassForInit


logger = logging.getLogger(__name__)


class WSHandler(metaclass=MetaClassForInit):
    heartbeat_timeout = 30
    connections = set()
    _on_message = {}

    @classmethod
    def cls_init(cls):
        cls.connections = set()
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
                                ret = await i(ws, send_json, data)
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
