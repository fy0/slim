import asyncio
import hashlib
import logging
import os
import time
import traceback
from dataclasses import dataclass, field
from email.utils import formatdate
from types import FunctionType
from typing import Dict, Any, TYPE_CHECKING, Sequence, Optional, Iterable, Union, Tuple, Callable, Awaitable, \
    AsyncIterator
from mimetypes import guess_type

import aiofiles
from multidict import CIMultiDict, istr
from multipart import multipart

from slim.base import const
from slim.base.types.route_meta_info import RouteStaticsInfo
from slim.exception import InvalidResponse
from slim.utils import async_call
from slim.utils.json_ex import json_ex_dumps
from slim.base.types.asgi import Scope, Receive, Send

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from slim import Application
    from slim.base._view.base_view import BaseView


def _to_str(s):
    if isinstance(s, bytes):
        return s.decode('utf-8')
    return s


class FileField:
    def __init__(self, field: multipart.File):
        self._field = field
        field.file_object.seek(0)

    @property
    def field_name(self):
        return _to_str(self._field.field_name)

    @property
    def file_name(self):
        return _to_str(self._field.file_name)

    @property
    def actual_file_name(self):
        return _to_str(self._field.actual_file_name)

    @property
    def file(self):
        return self._field.file_object

    @property
    def size(self):
        return self._field.size


@dataclass
class CORSOptions:
    host: str
    allow_credentials: bool = False
    expose_headers: Optional[Sequence] = None
    allow_headers: Sequence = ()
    max_age: Optional[int] = None
    allow_methods: Optional[Sequence] = '*'

    def pack_headers(self, request: 'ASGIRequest'):
        def solve(val):
            if isinstance(val, str):
                return val
            elif isinstance(val, Iterable):
                return ','.join(val)

        req_headers = request.headers

        headers = {
            const.ACCESS_CONTROL_ALLOW_ORIGIN: req_headers.get('origin'),
            const.ACCESS_CONTROL_ALLOW_CREDENTIALS: b'true' if self.allow_credentials else b'false'
        }

        if request.method == 'OPTIONS':
            if self.allow_headers:
                if self.allow_headers == '*':
                    headers[const.ACCESS_CONTROL_ALLOW_HEADERS] = req_headers.get('access-control-request-headers') or '*'
                else:
                    headers[const.ACCESS_CONTROL_ALLOW_HEADERS] = solve(self.allow_headers)

            if self.allow_methods:
                if self.allow_methods == '*':
                    headers[const.ACCESS_CONTROL_ALLOW_METHODS] = req_headers.get('access-control-request-method') or request.method
                else:
                    headers[const.ACCESS_CONTROL_ALLOW_METHODS] = self.allow_methods

        else:
            if self.expose_headers:
                # headers[const.ACCESS_CONTROL_EXPOSE_HEADERS] = solve(self.expose_headers)
                headers[const.ACCESS_CONTROL_EXPOSE_HEADERS] = b''

        if self.max_age:
            headers[const.ACCESS_CONTROL_MAX_AGE] = self.max_age

        return headers


@dataclass
class ASGIRequest:
    scope: Scope
    receive: Receive
    send: Send

    _headers_cache = None

    @property
    def method(self):
        return self.scope['method']

    @property
    def headers(self) -> CIMultiDict:
        """
        Get headers
        """
        if self._headers_cache is None:
            headers = CIMultiDict()
            for k, v in self.scope['headers']:
                k: bytes
                v: bytes
                headers.add(istr(k.decode('utf-8')), v.decode('utf-8'))
            self._headers_cache = headers
        return self._headers_cache


# StreamReadFunc = Callable[[], Awaitable[AsyncIterator[Tuple[bytes, bool]]]]  # data, has_more
StreamReadFunc = Callable[[], AsyncIterator[Tuple[bytes, bool]]]  # data, has_more


@dataclass
class Response:
    status: int = 200
    data: Union[str, bytes, StreamReadFunc] = b''
    headers: Dict[str, Any] = None
    content_type: str = 'text/plain'
    cookies: Dict[str, Dict] = None

    written: int = 0

    async def get_reader(self, data) -> StreamReadFunc:
        """
        Get reader function
        :return:
        """
        if asyncio.iscoroutinefunction(data):
            return data

        if isinstance(data, str):
            body = data.encode('utf-8')
        elif isinstance(data, bytes):
            body = data
        else:
            raise InvalidResponse()

        async def stream_read() -> AsyncIterator[Tuple[bytes, bool]]:
            yield body, False

        return stream_read

    def build_headers(self):
        headers = [
            # TODO: bytes convert cache
            [const.CONTENT_TYPE.encode('utf-8'), self.content_type.encode('utf-8')]
         ]

        if self.cookies:
            set_cookie = const.SET_COOKIE.encode('utf-8')
            for k, v in self.cookies.items():
                value = f"{v['name']}={v['value']}"

                if 'expires' in v:
                    value += f"; Expires={v['expires']}"

                if 'max-age' in v:
                    value += f"; Max-Age={v['max-age']}"

                if 'domain' in v:
                    value += f"; Domain={v['domain']}"

                if 'path' in v:
                    value += f"; Path={v['path']}"

                if v.get('secure'):
                    value += f"; Secure"

                if v.get('httponly'):
                    value += f"; HttpOnly"

                headers.append([set_cookie, value.encode('utf-8')])

        if self.headers:
            for k, v in self.headers.items():
                headers.append([k, v])

        headers_new = []
        for a, b in headers:
            if not isinstance(a, bytes):
                a = str(a).encode('utf-8')
            if not isinstance(b, bytes):
                b = str(b).encode('utf-8')
            headers_new.append([a, b])

        return headers_new

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = self.build_headers()
        reader = await self.get_reader(self.data)
        await send({
            "type": "http.response.start",
            "status": self.status,
            "headers": headers,
        })

        async for chunk, more_body in reader():
            self.written += len(chunk)
            ret = {
                "type": "http.response.body",
                "body": chunk
            }
            if more_body:
                ret["more_body"] = more_body
            await send(ret)


@dataclass
class JSONResponse(Response):
    data: Any = None
    content_type: str = 'application/json'
    json_dumps: FunctionType = json_ex_dumps

    async def get_reader(self, data) -> StreamReadFunc:
        data = self.json_dumps(data)
        return await super().get_reader(data)


@dataclass
class FileResponse(Response):
    static_file_path: str = None
    stat_result: os.stat_result = None

    content_type = None
    filename: str = None
    chunk_size = 4096
    headers: Dict[str, Any] = field(default_factory=lambda: {})

    def __post_init__(self):
        if self.content_type is None:
            self.content_type = guess_type(self.static_file_path)[0] or "text/plain"

        if not self.filename:
            self.filename = os.path.basename(self.static_file_path)

        if self.filename is not None:
            content_disposition = 'attachment; filename="{}"'.format(self.filename)
            self.headers.setdefault("content-disposition", content_disposition)

        if self.stat_result is not None:
            self.set_stat_headers(self.stat_result)

    def set_stat_headers(self, stat_result):
        content_length = str(stat_result.st_size)
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        etag_base = str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
        etag = hashlib.md5(etag_base.encode()).hexdigest()
        self.headers.setdefault("content-length", content_length)
        self.headers.setdefault("last-modified", last_modified)
        self.headers.setdefault("etag", etag)

    async def get_reader(self, data) -> StreamReadFunc:
        async def stream_read() -> AsyncIterator[Tuple[bytes, bool]]:
            async with aiofiles.open(self.static_file_path, mode="rb") as file:
                more_body = True
                while more_body:
                    chunk = await file.read(self.chunk_size)
                    more_body = len(chunk) == self.chunk_size
                    yield chunk, more_body

        return stream_read


async def handle_request(app: 'Application', scope: Scope, receive: Receive, send: Send, *, raise_for_resp=False):
    """
    Handle http request
    :param app:
    :param scope:
    :param receive:
    :param send:
    :return:
    """
    from ._view.abstract_sql_view import AbstractSQLView
    from ._view.validate import view_validate_check

    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                try:
                    app.prepare()
                    for func in app.on_startup:
                        await async_call(func)
                    app.running = True

                    # start timer
                    for interval_seconds, runner in app._timers_before_running:
                        loop = asyncio.get_event_loop()
                        loop.call_later(interval_seconds, runner)

                    await send({'type': 'lifespan.startup.complete'})
                except Exception:
                    traceback.print_exc()
                    await send({'type': 'lifespan.startup.failed'})
                    return

            elif message['type'] == 'lifespan.shutdown':
                for func in app.on_shutdown:
                    await async_call(func)

                await send({'type': 'lifespan.shutdown.complete'})
                return

    if scope['type'] == 'http':
        t = time.perf_counter()
        handler_name = None
        view = None

        request = ASGIRequest(scope, receive, send)
        resp = None

        try:
            if request.method == 'OPTIONS':
                resp = Response(200)
            else:
                route_info, call_kwargs_raw = app.route.query_path(scope['method'], scope['path'])

                if route_info:
                    handler_name = route_info.get_handler_name()

                    if isinstance(route_info, RouteStaticsInfo):
                        resp = await route_info.responder.solve(request, call_kwargs_raw.get('file'))
                    else:
                        # filter call_kwargs
                        call_kwargs = call_kwargs_raw.copy()
                        if route_info.names_varkw is not None:
                            for j in route_info.names_exclude:
                                if j in call_kwargs:
                                    del call_kwargs[j]

                        for j in call_kwargs.keys() - route_info.names_include:
                            del call_kwargs[j]

                        # build a view instance
                        view = await route_info.view_cls._build(app, request)
                        view._route_info = call_kwargs
                        app._last_view = view

                        if isinstance(view, AbstractSQLView):
                            view.current_interface = route_info.builtin_interface

                        # make the method bounded
                        handler = route_info.handler.__get__(view)

                        # note: view.prepare() may case finished
                        if not view.is_finished:
                            # user's validator check
                            await view_validate_check(view, route_info.va_query, route_info.va_post, route_info.va_headers)

                            ret_resp = None
                            if not view.is_finished:
                                # call the request handler
                                if asyncio.iscoroutinefunction(handler):
                                    view_ret = await handler(**call_kwargs)
                                else:
                                    view_ret = handler(**call_kwargs)

                                if not view.response:
                                    if isinstance(view_ret, Response):
                                        view.response = view_ret
                                    else:
                                        view.response = JSONResponse(200, view_ret)

                        resp = view.response

            if not resp:
                resp = Response(404, b"Not Found")

        except Exception as e:
            traceback.print_exc()
            resp = Response(500, b"Internal Server Error")

        try:
            # Configure CORS settings.
            if app.cors_options:
                # TODO: host match
                for i in app.cors_options:
                    i: CORSOptions
                    if resp.headers:
                        resp.headers.update(i.pack_headers(request))
                    else:
                        resp.headers = i.pack_headers(request)

            app._last_resp = resp
            await resp(scope, receive, send)

            took = round((time.perf_counter() - t) * 1000, 2)
            # GET /api/get -> TopicView.get 200 30ms
            path = scope['path']
            if scope['query_string']:
                path += '?' + scope['query_string'].decode('ascii')

            if view:
                view: BaseView
                await view._on_finish()

            if handler_name:
                logger.info("{} - {:15s} {:8s} {} -> {}, took {}ms".format(resp.status, scope['client'][0], scope['method'], path, handler_name, took))
            else:
                logger.info("{} - {:15s} {:8s} {}, took {}ms".format(resp.status, scope['client'][0], scope['method'], path, took))

            if view:  # for debug
                return view

        except Exception as e:
            if raise_for_resp:
                raise e
            else:
                traceback.print_exc()

    elif scope['type'] == 'websocket':
        request = ASGIRequest(scope, receive, send)
        route_info, call_kwargs_raw = app.route.query_ws_path(scope['path'])

        if route_info:
            # handler_name = route_info.get_handler_name()
            ws = route_info.ws_cls(app, request, call_kwargs_raw)
            await ws._prepare()
            await ws(scope, receive, send)
        else:
            # refuse connect
            await send({'type': 'websocket.close'})

    else:
        raise NotImplementedError(f"Unknown scope type {scope['type']}")
