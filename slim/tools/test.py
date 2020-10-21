import asyncio
import inspect
import json
import logging
from ipaddress import ip_address
from types import FunctionType
from typing import Optional, Union, Dict
from unittest import mock

from multidict import MultiDict, istr
from peewee import SqliteDatabase

from slim import Application
from slim.base.web import Response, JSONResponse
from slim.base.web.request import ASGIRequest
from slim.base.view.err_catch_context import ErrorCatchContext
from slim.base.types.route_meta_info import RouteInterfaceInfo
from slim.base.user import BaseUser
from slim.view import BaseView
from slim.exception import SlimException
from slim.utils import sentinel


def app_create(permission=None, log_level=logging.WARN, **kwargs) -> Application:
    """
    Get application instance
    :param permission:
    :param log_level:
    :param kwargs:
    :return:
    """
    app = Application(cookies_secret=b'123456', log_level=log_level, **kwargs)
    return app


def _polyfill_post(request: 'web.Request', post):
    if post:
        if isinstance(post, bytes):
            request._read_bytes = post
        else:
            try:
                request._read_bytes = bytes(json.dumps(post), 'utf-8')
            except TypeError:
                # logger.warning(...)
                pass

        if request.content_type == 'multipart/form-data':
            resp = _MockResponse(request.headers, _MockStream(post))
            mr = aiohttp.MultipartReader.from_response(resp)

            async def multipart():
                return mr

            request.multipart = multipart

    else:
        request._read_bytes = b''


def get_peewee_db():
    """
    Get peewee database instance
    :return:
    """
    db = SqliteDatabase(":memory:")
    return db


def make_mocked_request(method, path: str, *, headers: Dict[str, str] = None, body: bytes = None):
    path_split = path.split('?', 1)
    path = path_split[0]

    if len(path_split) > 1:
        query_string = path_split[1].encode('ascii', 'backslashreplace')
    else:
        query_string = b''

    scope = {
        'asgi': {'spec_version': '2.1', 'version': '3.0'},
        'client': ('127.0.0.1', 13284),
        'headers': [],
        'http_version': '1.1',
        'method': method,
        'path': path,
        'query_string': query_string,
        'raw_path': path.encode('utf-8'),
        'root_path': '',
        'scheme': 'http',
        'server': ('127.0.0.1', 5001),
        'type': 'http'
    }

    if headers:
        for k, v in headers.items():
            scope['headers'].append([k.encode('utf-8'), v.encode('utf-8')])

    async def receive():
        return {'body': body or b''}

    return ASGIRequest(scope, receive, mock.Mock())


async def make_mocked_view(app, view_cls, method, url, params=None, post=sentinel, *, headers=None, user=None,
                           content_type='application/json', body: Optional[bytes] = None)\
        -> Union[BaseView]:
    headers = headers or {}
    req = make_mocked_request(method, url, headers=headers, body=body)

    if content_type:
        headers['Content-Type'] = content_type

    async def hack_func(view):
        view._params_cache = params
        headers_cache = MultiDict()
        if not body:
            view._post_data_cache = post
        view._ip_cache = ip_address('127.0.0.1')
        view._current_user = user

        for k, v in headers.items():
            headers_cache[istr(k)] = v

        view.request._headers_cache = headers_cache

    if not isinstance(view_cls, BaseView):
        view = await view_cls._build(app, req, _hack_func=hack_func)
    else:
        view = view_cls
        view.request = req
        view.app = app
        await hack_func(view)

        with ErrorCatchContext(view):
            await view._prepare()

    return view


async def invoke_interface(app: Application, func: FunctionType, params=None, post=sentinel, *, headers=None,
                           method=None, user=None, bulk=False, returning=None, role=None, body: Optional[bytes] = None,
                           content_type='application/json') -> Optional[BaseView]:
    """
    Invoke a interface programmatically
    :param app: Application object
    :param func: the interface function
    :param params: http params
    :param post: http post body
    :param headers: http headers
    :param method: auto detect
    :param user: current user
    :param bulk: is bulk operation
    :param returning:
    :param role:
    :param content_type:
    :return:
    """
    url = 'mock_url'

    if user:
        assert isinstance(user, BaseUser), 'user must be a instance of `BaseUser`'

    if not getattr(func, '_route_info', None):
        raise SlimException('invoke failed, not interface: %r' % func)

    meta: RouteInterfaceInfo = getattr(func, '_route_info')
    assert meta.view_cls, 'invoke only work after app.prepare()'

    func_is_method = inspect.ismethod(func)

    if func_is_method:
        handler = func
        view = func.__self__
    else:
        if len(meta.view_cls_set) > 1:
            # TODO: multi sqlview classes exists for this interface, please specified the sqlview class you want
            pass

        view = meta.view_cls
        handler = func

    headers = headers or {}
    if bulk:
        headers['bulk'] = bulk
    if role:
        headers['role'] = role
    if returning:
        headers['returning'] = 'true'

    _method = method if method else meta.methods[0]

    view = await make_mocked_view(app, view, _method, url, params=params, post=post, headers=headers,
                                  body=body, content_type=content_type, user=user)

    if not func_is_method:
        handler = handler.__get__(view)

    # url = info.route.fullpath
    # _method = next(iter(info.route.method))

    # note: sqlview.prepare() may case finished
    if not view.is_finished:
        # user's validator check
        from slim.base.view.validate import view_validate_check
        await view_validate_check(view, meta.va_query, meta.va_post, meta.va_headers)

        if not view.is_finished:
            # call the request handler
            if asyncio.iscoroutinefunction(handler):
                view_ret = await handler()
            else:
                view_ret = handler()

            if not view.response:
                if isinstance(view_ret, Response):
                    view.response = view_ret
                else:
                    view.response = JSONResponse(200, view_ret)

            return view


async def make_mocked_ws_request(url):
    scope = {
        'type': 'websocket',
        'asgi': {'version': '3.0', 'spec_version': '2.1'},
        'scheme': 'ws',
        'server': ('127.0.0.1', 8007),
        'client': ('127.0.0.1', 52194),
        'root_path': '',
        'path': url,
        'raw_path': url,
        'query_string': b'',
        'headers': [
            (b'host', b'127.0.0.1:8007'),
            (b'connection', b'Upgrade'),
            (b'pragma', b'no-cache'),
            (b'cache-control', b'no-cache'),
            (b'upgrade', b'websocket'),
            (b'sec-websocket-version', b'13'),
            (b'accept-encoding', b'gzip, deflate, br'),
            (b'accept-language', b'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'),
            (b'sec-websocket-key', b'C8SUrcM0+ev3kR8TE7P62w=='),
            (b'sec-websocket-extensions', b'permessage-deflate; client_max_window_bits')
        ],
        'subprotocols': []
    }

    recv_lst = [
        {'type': 'websocket.connect'},
        {'type': 'websocket.disconnect', 'code': 1001}
    ]

    async def receive():
        if recv_lst:
            return recv_lst.pop(0)

    async def send(message):
        pass

    return ASGIRequest(scope, receive, send)
