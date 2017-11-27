import json
import logging
import aiohttp
from aiohttp import web
from ..utils import MetaClassForInit


logger = logging.getLogger(__name__)


class WSHandler(metaclass=MetaClassForInit):
    connections = []
    on_message = {}

    @classmethod
    def cls_init(cls):
        cls.connections = []
        cls.on_message = {}

    @classmethod
    def route(cls, command):
        def _(obj):
            cls.on_message.setdefault(command, [])
            cls.on_message[command].append(obj)
        return _

    def __init__(self):
        self.ws = None

    async def _handle(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.connections.append(self)
        self.ws = ws

        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == 'ws.close':
                    await ws.close()
                else:
                    # request id, head, data
                    rid, command, data = json.loads(msg.data)

                    async def send_json(code, data):
                        await ws.send_json([rid, {'code': code, 'data': data}])

                    if command in self.on_message:
                        for i in self.on_message[command]:
                            ret = await i(self, send_json, data)
                            if ret is not None:
                                await send_json(*ret)

            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.debug('ws connection closed with exception %s' % ws.exception())

        logger.debug('websocket connection closed')
        return ws
