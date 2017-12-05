import json
import logging
import aiohttp
from aiohttp import web
from aiohttp.web_request import BaseRequest

from slim.retcode import RETCODE
from ..utils import MetaClassForInit


logger = logging.getLogger(__name__)


class WSHandler(metaclass=MetaClassForInit):
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
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        ws.request = request
        self.connections.add(ws)
        wsid = ws.headers['Sec-Websocket-Accept']
        logger.debug('websocket connected: %r, %d user(s) online' % (wsid, len(self.connections)))

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == 'ws.close':
                    await ws.close()
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

        self.connections.remove(ws)
        await self.on_close(ws)
        logger.debug('websocket connection closed: %r, %d user(s) online' % (wsid, len(self.connections)))
        return ws
