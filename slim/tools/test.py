import asyncio
import inspect
import io
import json
import logging
from ipaddress import ip_address
from types import FunctionType
from typing import Optional, Callable, Union
from unittest import mock

import aiohttp
from aiohttp import web
from aiohttp.test_utils import make_mocked_request as _make_mocked_request
from peewee import SqliteDatabase

from slim import Application, ALL_PERMISSION
from slim.base._view.abstract_sql_view import AbstractSQLView
from slim.base._view.err_catch_context import ErrorCatchContext
from slim.base.types.route_meta_info import RouteInterfaceInfo
from slim.base.user import BaseUser
from slim.base.view import BaseView
from slim.exception import SlimException
from slim.support.peewee import PeeweeView


def new_app(permission=ALL_PERMISSION, log_level=logging.WARN, **kwargs) -> Application:
    """
    Get application instance
    :param permission:
    :param log_level:
    :param kwargs:
    :return:
    """
    app = Application(cookies_secret=b'123456', permission=permission, log_level=log_level, **kwargs)
    return app


class _MockResponse:
    def __init__(self, headers, content):
        self.headers = headers
        self.content = content

    async def release(self):
        pass


class _MockStream:
    def __init__(self, content):
        self.content = io.BytesIO(content)

    async def read(self, size=None):
        return self.content.read(size)

    def at_eof(self):
        return self.content.tell() == len(self.content.getbuffer())

    async def readline(self):
        return self.content.readline()

    def unread_data(self, data):
        self.content = io.BytesIO(data + self.content.read())


def _polyfill_post(request: web.Request, post):
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


async def make_mocked_view_instance(app, view_cls, method, url, params=None, post=None, *, headers=None,
                                    content_type='application/json') -> Union[BaseView, AbstractSQLView, PeeweeView]:
    if not headers:
        headers = {}

    if content_type:
        headers['Content-Type'] = content_type

    request = _make_mocked_request(method, url, headers=headers, protocol=mock.Mock(), app=app)
    _polyfill_post(request, post)

    view = view_cls(app, request)
    view._params_cache = params
    view._post_data_cache = post

    await view.prepare()
    return view


async def invoke_interface(app: Application, func: FunctionType, params=None, post=None, *, headers=None, method=None,
                           user=None, bulk=False, returning=None, role=None, content_type='application/json',
                           fill_post_cache=True) -> Optional[BaseView]:
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
    :param fill_post_cache:
    :return:
    """
    url = 'mock_url'

    if user:
        assert isinstance(user, BaseUser), 'user must be a instance of `BaseUser`'

    if not getattr(func, '_route_info', None):
        raise SlimException('invoke failed, not interface: %r' % func)

    meta: RouteInterfaceInfo = getattr(func, '_route_info')
    assert meta.view_cls, 'invoke only work after app.prepare()'

    if inspect.ismethod(func):
        handler = func
        view = func.__self__
    else:
        view = meta.view_cls(app)
        handler = func.__get__(view)

    view._req = 1
    view.app = app

    headers = headers or {}
    if bulk:
        headers['bulk'] = bulk
    if role:
        headers['role'] = role
    if returning:
        headers['returning'] = 'true'

    if content_type:
        headers['Content-Type'] = content_type

    view._params_cache = params
    view._headers_cache = headers
    if fill_post_cache:
        view._post_data_cache = post
    view._ip_cache = ip_address('127.0.0.1')
    view._current_user = user

    with ErrorCatchContext(view):
        await view._prepare()

    _method = method if method else meta.method

    # url = info.route.fullpath
    # _method = next(iter(info.route.method))

    # note: view.prepare() may case finished
    if not view.is_finished:
        # user's validator check
        from slim.base._view.validate import view_validate_check
        await view_validate_check(view, meta.va_query, meta.va_post, meta.va_headers)

        if not view.is_finished:
            # call the request handler
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

            return view


def make_asgi_request(method):
    return {
        'asgi': {'spec_version': '2.1', 'version': '3.0'},
        'client': ('127.0.0.1', 13284),
        'headers': [(b'connection', b'keep-alive'),
                    (b'user-agent', b'slim tester'),
                    (b'accept-encoding', b'gzip, deflate, br'),
                    (b'cookie', b'A=1')],
        'http_version': '1.1',
        'method': method,
        'path': '/',
        'query_string': b'asdasd=123&b=2&b=3&c=4',
        'raw_path': b'/',
        'root_path': '',
        'scheme': 'http',
        'server': ('127.0.0.1', 5001),
        'type': 'http'
    }
