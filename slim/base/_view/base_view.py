import asyncio
import json
import logging
import time
from collections import OrderedDict
from io import BytesIO
from typing import Set, List, Union, Optional, Dict, Mapping, Any
from urllib.parse import parse_qs
from ipaddress import IPv4Address, IPv6Address, ip_address
from multidict import MultiDict, CIMultiDict, istr
from multipart import multipart
from yarl import URL

from ..app import Application
from ..types.route_meta_info import RouteViewInfo
from ..web import ASGIRequest, Response, JSONResponse, FileField, StreamReadFunc, FileResponse
from ...base import const
from ...base._view.err_catch_context import ErrorCatchContext
from ...base.const import CONTENT_TYPE
from ...base.helper import create_signed_value, decode_signed_value
from ...base.permission import Permissions
from ...base.types.temp_storage import TempStorage
from ...base.user import BaseUser, BaseUserViewMixin
from ...exception import NoUserViewMixinException, InvalidPostData
from ...ext.decorator import deprecated
from ...retcode import RETCODE

from ...utils import MetaClassForInit, async_call, sentinel, sync_call
from ...utils.cookies import cookie_parser
from ...utils.json_ex import json_ex_dumps

logger = logging.getLogger(__name__)


class HTTPMixin:
    def __init__(self, app: Application = None, req: ASGIRequest = None):
        self.app = app
        self.request: Optional[ASGIRequest] = req

        self._ip_cache = None
        self._cookies_cache = None
        self._params_cache = None
        self._current_user = None
        self._current_user_roles = None

        self._cookie_set = OrderedDict()

    def _check_req(self):
        assert self.request, 'no request found'

    @property
    def path(self):
        return self.request.scope['path']

    @property
    def method(self) -> str:
        self._check_req()
        return self.request.scope['method']

    async def get_x_forwarded_for(self) -> List[Union[IPv4Address, IPv6Address]]:
        lst = self.headers.getall(const.X_FORWARDED_FOR, [])
        if not lst: return []
        lst = map(str.strip, lst[0].split(','))
        return [ip_address(x) for x in lst if x]

    async def get_ip(self) -> Union[IPv4Address, IPv6Address]:
        """
        get ip address of client
        :return:
        """
        if not self._ip_cache:
            xff = await self.get_x_forwarded_for()
            if xff:
                return xff[0]
            ip_addr = self.request.scope['client'][0]
            self._ip_cache = ip_address(ip_addr)
        return self._ip_cache

    @property
    def can_get_user(self):
        return isinstance(self, BaseUserViewMixin)

    @property
    def current_user(self) -> BaseUser:
        if not self.can_get_user:
            raise NoUserViewMixinException("Current View should inherited from `BaseUserViewMixin` or it's subclasses")
        if not self._current_user:
            func = getattr(self, 'get_current_user', None)
            if func:
                # 只加载非异步函数
                if not asyncio.iscoroutinefunction(func):
                    self._current_user = func()
                # async function:
                # RuntimeError: This event loop is already running
            else:
                self._current_user = None
        return self._current_user

    @property
    def roles(self) -> Set:
        if not self.can_get_user:
            raise NoUserViewMixinException("Current View should inherited from `BaseUserViewMixin` or it's subclasses")
        if self._current_user_roles is not None:
            return self._current_user_roles
        else:
            u = self.current_user
            self._current_user_roles = {None} if u is None else set(u.roles)
            return self._current_user_roles

    @property
    def params(self) -> "MultiDict[str]":
        """
        get query parameters
        :return:
        """
        self._check_req()
        if self._params_cache is None:
            self._params_cache = URL('?' + self.request.scope['query_string'].decode('utf-8')).query
        return self._params_cache

    @property
    def content_type(self) -> str:
        return self.headers.get(CONTENT_TYPE)

    @property
    def cookies(self) -> Mapping[str, str]:
        if self._cookies_cache is not None:
            return self._cookies_cache
        self._cookies_cache = cookie_parser(self.headers.get('cookie', ''))
        return self._cookies_cache

    def get_cookie(self, name, default=None) -> Optional[str]:
        """
        Get cookie from request.
        """
        if name in self._cookie_set:
            cookie = self._cookie_set.get(name)
            if cookie['max_age'] != 0:
                return cookie
        return self.cookies.get(name, default)

    @property
    def headers(self) -> CIMultiDict:
        """
        Get headers
        """
        self._check_req()
        return self.request.headers

    async def _prepare(self):
        # 如果获取用户是一个异步函数，那么提前将其加载
        if self.can_get_user:
            func = getattr(self, 'get_current_user', None)
            if func:
                if asyncio.iscoroutinefunction(func):
                    self._current_user = await func()


class BaseView(HTTPMixin, metaclass=MetaClassForInit):
    """
    Basic http view object.
    """
    _no_route = False

    _route_info: Optional['RouteViewInfo']
    _interface_disable: Set[str]
    ret_val: Optional[Dict]

    @classmethod
    def cls_init(cls):
        cls._interface_disable = set()

    @classmethod
    def unregister(cls, name):
        """ interface unregister"""
        cls._interface_disable.add(name)

    @property
    def permission(self) -> Permissions:
        return self.app.permission

    @classmethod
    def _on_bind(cls, route):
        pass

    def __init__(self, app: Application = None, req: ASGIRequest = None):
        super().__init__(app, req)

        self.ret_val = None
        self.response: Optional[Response] = None
        self.session = None

        self._legacy_route_info_cache = {}

        self._post_data_cache = sentinel
        self._ = self.temp_storage = TempStorage()

    @classmethod
    async def _build(cls, app, request: ASGIRequest, *, _hack_func=None) -> 'BaseView':
        """
        Create a view, and bind request data
        :return:
        """
        view = cls(app, request)

        if _hack_func:
            await _hack_func(view)

        with ErrorCatchContext(view):
            await view._prepare()

        return view

    @property
    def is_finished(self):
        return self.response is not None

    async def _prepare(self):
        await super()._prepare()
        session_cls = self.app.options.session_cls
        self.session = await session_cls.get_session(self)
        await async_call(self.prepare)

    async def prepare(self):
        pass

    async def _on_finish(self):
        if self.session:
            await self.session.save()

        await async_call(self.on_finish)

        if self.response:
            if isinstance(self.response, JSONResponse):
                if self.response.written > 200:
                    logger.debug('finish: json (%d bytes)' % self.response.written)
                else:
                    logger.debug('finish: json, %s' % json_ex_dumps(self.ret_val))
            elif isinstance(self.response, FileResponse):
                logger.debug('finish: file (%d bytes)' % self.response.written)
            else:
                logger.debug('finish: (%d bytes)' % self.response.written)

    async def on_finish(self):
        pass

    @property
    def retcode(self):
        if self.is_finished:
            return self.ret_val['code']

    def finish(self, code: int, data=sentinel, msg=sentinel, *, headers=None):
        """
        Set response as {'code': xxx, 'data': xxx}
        :param code: Result code
        :param data: Response data
        :param msg: Message, optional
        :param headers: Response header
        :return:
        """
        if data is sentinel:
            data = RETCODE.txt_cn.get(code, None)
        if msg is sentinel and code != RETCODE.SUCCESS:
            msg = RETCODE.txt_cn.get(code, None)
        body = {'code': code, 'data': data}  # for access in inhreads method
        if msg is not sentinel:
            body['msg'] = msg

        self.ret_val = body
        self.response = JSONResponse(data=body, json_dumps=json_ex_dumps, headers=headers, cookies=self._cookie_set)

    def finish_json(self, data: Any, *, status: int = 200, headers=None):
        self.ret_val = data
        self.response = JSONResponse(data=data, json_dumps=json_ex_dumps, headers=headers, status=status,
                                     cookies=self._cookie_set)

    def finish_raw(self, data: Union[bytes, str, StreamReadFunc] = b'', status: int = 200, content_type: str = 'text/plain', *,
                   headers=None):
        """
        Set raw response
        :param headers:
        :param data:
        :param status:
        :param content_type:
        :return:
        """
        self.ret_val = data
        self.response = Response(data=data, status=status, content_type=content_type, headers=headers, cookies=self._cookie_set)

    async def post_data(self) -> "Optional[Mapping[str, Union[str, bytes, 'FileField']]]":
        """
        :return: 在有post的情况下必返回Mapping，否则返回None
        """
        if self._post_data_cache is not sentinel:
            return self._post_data_cache

        async def read_body(receive):
            # TODO: fit content-length
            body_buf = BytesIO()
            more_body = True
            max_size = self.app.client_max_size
            cur_size = 0

            while more_body:
                message = await receive()
                cur_size += body_buf.write(message.get('body', b''))
                if cur_size > max_size:
                    raise Exception('body size limited')
                more_body = message.get('more_body', False)

            body_buf.seek(0)
            return body_buf

        if self.content_type in ('application/json', '', None):
            try:
                body_buffer = await read_body(self.request.receive)
                body = body_buffer.read()
                if body:
                    self._post_data_cache = json.loads(body)
                    if not isinstance(self._post_data_cache, Mapping):
                        raise InvalidPostData('post data should be a mapping.')
                else:
                    return None
            except json.JSONDecodeError as e:
                raise InvalidPostData('json decoded failed')

        elif self.content_type == 'application/x-www-form-urlencoded':
            body_buffer = await read_body(self.request.receive)

            post = MultiDict()
            for k, v in parse_qs(body_buffer.read().decode('utf-8')).items():
                for j in v:
                    post.add(k, j)
            self._post_data_cache = post
        else:
            async def read_multipart(receive):
                more_body = True
                max_size = self.app.client_max_size
                cur_size = 0

                while more_body:
                    message = await receive()
                    chunk = message.get('body', b'')
                    cur_size += len(chunk)
                    parser.write(chunk)
                    if cur_size > max_size:
                        raise Exception('body size limited')
                    more_body = message.get('more_body', False)

            post = MultiDict()

            def on_field(field: multipart.Field):
                post.add(field.field_name.decode('utf-8'), field.value.decode('utf-8'))

            def on_file(field: multipart.File):
                post.add(field.field_name.decode('utf-8'), FileField(field))

            parser = multipart.create_form_parser({'Content-Type': self.content_type}, on_field, on_file)
            await read_multipart(self.request.receive)
            self._post_data_cache = post

        return self._post_data_cache

    def set_cookie(self, name, value, *, path=None, expires=None, domain=None, max_age=None, secure=None,
                   httponly=None, version=None):
        """
        Set Cookie
        https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies
        """
        key = (name, domain, path)
        info_full = {'name': name, 'value': value, 'path': path, 'expires': expires, 'domain': domain,
                     'max-age': max_age, 'secure': secure, 'httponly': httponly, 'version': version}

        info = dict(filter(lambda x: x[1] is not None, info_full.items()))
        self._cookie_set[key] = info

    def del_cookie(self, name, *, domain: Optional[str] = None, path: Optional[str] = None):
        """
        Delete cookie.
        """
        self.set_cookie(name, '', max_age=0, expires='Thu, 01 Jan 1970 00:00:00 GMT', domain=domain, path=path)

    def set_secure_cookie(self, name, value, *, httponly=True, max_age=30 * 24 * 60 * 60):
        #  一般来说是 UTC
        # https://stackoverflow.com/questions/16554887/does-pythons-time-time-return-a-timestamp-in-utc
        timestamp = int(time.time())
        # version, utctime, name, value
        # assert isinatance(value, (str, list, tuple, bytes, int))
        to_sign = [1, timestamp, name, value]
        secret = self.app.options.cookies_secret
        self.set_cookie(name, create_signed_value(secret, to_sign), max_age=max_age, httponly=httponly)

    def get_secure_cookie(self, name, default=None, max_age_days=31):
        secret = self.app.options.cookies_secret
        value = self.get_cookie(name)
        if value:
            data = decode_signed_value(secret, value)
            # TODO: max_age_days 过期计算
            if data and data[2] == name:
                return data[3]
        return default

    @property
    @deprecated('deprecated, use function arguments to instead')
    def route_info(self):
        """
        info matched by router
        :return:
        """
        return self._legacy_route_info_cache

    @classmethod
    def _ready(cls):
        """ private version of cls.ready() """
        sync_call(cls.ready)

    @classmethod
    def ready(cls):
        """
        All modules loaded, and ready to serve.
        Emitted after register routes and before loop start
        :return:
        """
        pass

