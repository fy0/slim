import asyncio
from collections import OrderedDict
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Optional, List, Union, Set, Mapping

import typing
from multidict import CIMultiDict
from yarl import URL

from slim.base import const
from slim.base.const import CONTENT_TYPE
from slim.base.user import BaseUserViewMixin, BaseUser
from slim.base.web import ASGIRequest
from slim.exception import NoUserViewMixinException
from slim.utils.cookies import cookie_parser

if typing.TYPE_CHECKING:
    from slim import Application


class HTTPMixin:
    def __init__(self, app: 'Application' = None, req: ASGIRequest = None):
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