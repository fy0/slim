import json
import logging
import time
from io import BytesIO
from typing import Set, Union, Optional, Dict, Mapping, Any
from urllib.parse import parse_qs
from multidict import MultiDict, istr
from multipart import multipart

from ..app import Application
from ..types.route_meta_info import RouteViewInfo, RouteInterfaceInfo
from ..web.http_mixin import HTTPMixin
from ..web.response import StreamReadFunc, Response, JSONResponse, FileResponse
from ..web.request import ASGIRequest
from ..web.staticfile import FileField
from ...base.view.err_catch_context import ErrorCatchContext
from slim.utils.data_sign import create_signed_value, decode_signed_value
from ...base.types.temp_storage import TempStorage
from ...exception import InvalidPostData
from ...ext.decorator import deprecated

from ...utils import MetaClassForInit, async_call, sentinel, sync_call
from ...utils.json_ex import json_ex_dumps

logger = logging.getLogger(__name__)


class BaseView(HTTPMixin, metaclass=MetaClassForInit):
    """
    Basic http view object.
    """
    _no_route = False

    _route_info: Optional['RouteInterfaceInfo']
    _interface_disable: Set[str]

    @classmethod
    def cls_init(cls):
        cls._interface_disable = set()

    @classmethod
    def unregister(cls, name):
        """ interface unregister"""
        cls._interface_disable.add(name)

    @classmethod
    def _on_bind(cls, route):
        pass

    def __init__(self, app: Application = None, req: ASGIRequest = None):
        super().__init__(app, req)

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

    @property
    def current_role(self) -> Optional[Any]:
        return None

    @property
    def current_request_role(self) -> Optional[str]:
        """
        Current role requesting by client.
        :return:
        """
        return self.headers.get(istr('Role'), None)

    async def _prepare(self):
        await super()._prepare()
        # session_cls = self.app.options.session_cls
        # self.session = await session_cls.get_session(self)
        await async_call(self.prepare)

    @classmethod
    async def on_init(cls):
        pass

    async def prepare(self):
        pass

    async def _on_finish(self):
        # if self.session:
        #     await self.session.save()

        await async_call(self.on_finish)

        if self.response:
            if isinstance(self.response, JSONResponse):
                if self.response.written > 200:
                    logger.debug('finish: json (%d bytes)' % self.response.written)
                else:
                    logger.debug('finish: json, %s' % json_ex_dumps(self.response.data))
            elif isinstance(self.response, FileResponse):
                logger.debug('finish: file (%d bytes)' % self.response.written)
            else:
                logger.debug('finish: (%d bytes)' % self.response.written)

    async def on_finish(self):
        pass

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

        if (isinstance(self.content_type, str) and self.content_type.startswith('application/json')) or self.content_type in ('application/json', '', None):
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
        secret = self.app.cookies_secret
        self.set_cookie(name, create_signed_value(secret, to_sign), max_age=max_age, httponly=httponly)

    def get_secure_cookie(self, name, default=None, max_age_days=31):
        secret = self.app.cookies_secret
        value = self.get_cookie(name)
        if value:
            data = decode_signed_value(secret, value)
            # TODO: max_age_days 过期计算
            if data and data[2] == name:
                return data[3]
        return default
