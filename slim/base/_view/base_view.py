import asyncio
import logging
import time
from types import FunctionType
from typing import Set, List, Union, Optional, Dict
from unittest import mock

from aiohttp import hdrs, web
from ipaddress import IPv4Address, IPv6Address, ip_address

from aiohttp.web_request import BaseRequest
from multidict import MultiDict, CIMultiDictProxy

from slim import Application, json_ex_dumps
from slim.base.helper import create_signed_value, decode_signed_value
from slim.base.permission import Permissions
from slim.base.types.temp_storage import TempStorage
from slim.base.user import BaseUser, BaseUserViewMixin
from slim.exception import NoUserViewMixinException
from slim.retcode import RETCODE

from slim.utils import MetaClassForInit, async_call, sentinel, sync_call
from slim.utils.jsdict import JsDict

logger = logging.getLogger(__name__)


class BaseView(metaclass=MetaClassForInit):
    """
    应在 cls_init 时完成全部接口的扫描与wrap函数创建
    并在wrapper函数中进行实例化，传入 request 对象
    """
    _interface = {}
    _no_route = False

    ret_val: Optional[Dict]
    ret_headers: Optional[Dict]

    @classmethod
    def _use(cls, name, method: [str, Set, List], url=None, summary=None, *,
             _sql_query=False, _sql_post=False, _inner_name=None,
             va_query=None, va_post=None, va_headers=None, va_resp=None, deprecated=False):
        if not isinstance(method, (str, list, set, tuple)):
            raise BaseException('Invalid type of method: %s' % type(method).__name__)

        if isinstance(method, str):
            method = {method}

        def solve(value):
            if _sql_query or _sql_post:
                value['_sql'] = {
                    'query': _sql_query,
                    'post': _sql_post,
                }
            return value

        # TODO: check methods available
        cls._interface[name] = [solve({'method': method, 'url': url, 'summary': summary, 'inner_name': _inner_name,
                                       'va_query': va_query, 'va_post': va_post, 'va_headers': va_headers,
                                       'va_resp': va_resp, 'deprecated': deprecated})]

    @classmethod
    def use(cls, name, method: [str, Set, List], url=None, summary=None, va_query=None, va_post=None,
            va_headers=None, va_resp=None, deprecated=False):
        """ interface register function"""
        return cls._use(name, method, url=url, summary=summary, va_query=va_query, va_post=va_post,
                        va_headers=va_headers, va_resp=va_resp, deprecated=deprecated)

    @classmethod
    def _use_lst(cls, name, *, _sql_query=False, _sql_post=False, _inner_name=None, _inner_name_with_size=None,
                 summary=None, summary_with_size=None,
                 va_query=None, va_post=None, va_headers=None, va_resp=None, deprecated=False):
        def solve(value):
            if _sql_query or _sql_post:
                value['_sql'] = {
                    'query': _sql_query,
                    'post': _sql_post,
                }
            return value

        cls._interface[name] = [
            solve({'method': {'GET'}, 'url': '%s/{page}' % name, 'summary': summary, 'inner_name': _inner_name,
                   'va_query': va_query, 'va_post': va_post, 'va_headers': va_headers,
                   'va_resp': va_resp, 'deprecated': deprecated}),
            solve({'method': {'GET'}, 'url': '%s/{page}/{size}' % name, 'summary': summary_with_size, 'inner_name': _inner_name_with_size,
                   'va_query': va_query, 'va_post': va_post, 'va_headers': va_headers,
                   'va_resp': va_resp, 'deprecated': deprecated}),
        ]

    @classmethod
    def use_lst(cls, name, summary=None, va_query=None, va_post=None, va_headers=None, va_resp=None, deprecated=False):
        return cls.use_lst(name, summary=summary, va_query=va_query, va_post=va_post,
                           va_headers=va_headers, va_resp=va_resp, deprecated=deprecated)

    @classmethod
    def unregister(cls, name):
        """ interface unregister"""
        cls._interface.pop(name, None)

    @classmethod
    def interface_register(cls):
        pass

    discard = unregister
    interface = interface_register

    @classmethod
    def cls_init(cls):
        cls._interface = {}
        cls.interface_register()

        # compatible with old version
        if getattr(cls, 'interface', None):
            cls.interface()

        for k, v in vars(cls).items():
            if isinstance(v, FunctionType):
                if getattr(v, '_interface', None):
                    method, url, meta = v._interface
                    cls.use(k, method, url, **meta)

    @property
    def permission(self) -> Permissions:
        return self.app.permission

    def __init__(self, app: Application = None, aiohttp_request: BaseRequest = None):
        self.app = app
        if aiohttp_request is None:
            self._request = mock.Mock()
        else:
            self._request = aiohttp_request

        self.ret_val = None
        self.ret_headers = None
        self.response = None
        self.session = None
        self._ip_cache = None
        self._cookie_set = None
        self._params_cache = None
        self._post_data_cache = None
        self._post_json_cache = None
        self._current_user = None
        self._current_user_roles = None
        self._ = self.temp_storage = TempStorage()

    @property
    def is_finished(self):
        return self.response is not None

    async def _prepare(self):
        # 如果获取用户是一个异步函数，那么提前将其加载
        if self.can_get_user:
            func = getattr(self, 'get_current_user', None)
            if func:
                if asyncio.iscoroutinefunction(func):
                    self._current_user = await func()

        session_cls = self.app.options.session_cls
        self.session = await session_cls.get_session(self)
        await async_call(self.prepare)

    async def prepare(self):
        pass

    async def _on_finish(self):
        if self.session:
            await self.session.save()

        await async_call(self.on_finish)

        if isinstance(self.ret_val, bytes):
            logger.debug('finish: raw body(%d bytes)' % len(self.ret_val))
        else:
            logger.debug('finish: %s' % self.ret_val)

    async def on_finish(self):
        pass

    @property
    def method(self):
        return self._request.method

    async def get_x_forwarded_for(self) -> List[Union[IPv4Address, IPv6Address]]:
        lst = self._request.headers.getall(hdrs.X_FORWARDED_FOR, [])
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
            if xff: return xff[0]
            ip_addr = self._request.transport.get_extra_info('peername')[0]
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
    def retcode(self):
        if self.is_finished:
            return self.ret_val['code']

    def _finish_end(self):
        for i in self._cookie_set or ():
            if i[0] == 'set':
                self.response.set_cookie(i[1], i[2], **i[3])
            else:
                self.response.del_cookie(i[1])

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
        self.ret_val = {'code': code, 'data': data}  # for access in inhreads method
        if msg is not sentinel:
            self.ret_val['msg'] = msg
        self.ret_headers = headers
        self.response = web.json_response(self.ret_val, dumps=json_ex_dumps, headers=headers)
        self._finish_end()

    def finish_raw(self, body: bytes, status: int = 200, content_type: Optional[str] = None, *, headers=None):
        """
        Set raw response
        :param headers:
        :param body:
        :param status:
        :param content_type:
        :return:
        """
        self.ret_val = body
        self.response = web.Response(body=body, status=status, content_type=content_type, headers=headers)
        self._finish_end()

    def del_cookie(self, key):
        if self._cookie_set is None:
            self._cookie_set = []
        self._cookie_set.append(('del', key))

    @property
    def params(self) -> "MultiDict[str]":
        if self._params_cache is None:
            self._params_cache = MultiDict(self._request.query)
        return self._params_cache

    async def _post_json(self) -> dict:
        # post body: raw(text) json
        if self._post_json_cache is None:
            self._post_json_cache = dict(await self._request.json())
        return self._post_json_cache

    async def post_data(self) -> "MultiDict[Union[str, bytes, FileField]]":
        if self.method not in BaseRequest.POST_METHODS:
            return MultiDict()

        if self._post_data_cache is not None:
            return self._post_data_cache
        if self._request.content_type == 'application/json':
            # post body: raw(text) json
            test_post = getattr(self._request, '_post', sentinel)
            if test_post is not sentinel:
                self._post_data_cache = test_post
            else:
                # aiohttp 的 Mock 函数无法维持json()运作
                self._post_data_cache = await self._request.json()
        else:
            # post body: form data
            self._post_data_cache = await self._request.post()
        return self._post_data_cache

    def set_cookie(self, key, value, *, path='/', expires=None, domain=None, max_age=None, secure=None,
                   httponly=None, version=None):
        if self._cookie_set is None:
            self._cookie_set = []
        kwargs = {'path': path, 'expires': expires, 'domain': domain, 'max_age': max_age, 'secure': secure,
                  'httponly': httponly, 'version': version}
        self._cookie_set.append(('set', key, value, kwargs))

    def get_cookie(self, name, default=None):
        if self._request.cookies is not None and name in self._request.cookies:
            return self._request.cookies.get(name, default)
        return default

    def set_secure_cookie(self, name, value: bytes, *, httponly=True, max_age=30):
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
    def headers(self) -> CIMultiDictProxy:
        self._request: web.Request
        return self._request.headers

    @property
    def route_info(self):
        """
        info matched by router
        :return:
        """
        self._request: web.Request
        return self._request.match_info

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
