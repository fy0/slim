import base64
import hashlib
import hmac
import logging
from asyncio import iscoroutinefunction
from typing import Iterable
from aiohttp import web, web_response
from ..utils import msgpack, async_run
from posixpath import join as urljoin


logger = logging.getLogger(__name__)
# __all__ = ('Route',)


def view_bind(app, url, view_cls):
    """
    将 API 绑定到 web 服务上
    :param view_cls: 
    :param app: 
    :param url: 
    :return: 
    """
    url = url or view_cls.__class__.__name__.lower()

    def wrap(func):
        # noinspection PyProtectedMember
        async def wfunc(request):
            view_instance = view_cls(request)
            handler_name = '%s.%s' % (view_cls.__name__, func.__name__)
            ascii_encodable_path = request.path.encode('ascii', 'backslashreplace').decode('ascii')
            logger.info("{} {} -> {}".format(request._method, ascii_encodable_path, handler_name))

            await view_instance._prepare()
            if view_instance.is_finished:
                return view_instance.response
            await view_instance.prepare()
            if view_instance.is_finished:
                return view_instance.response

            assert iscoroutinefunction(func), "Add 'async' before interface function %r" % handler_name
            resp = await func(view_instance) or view_instance.response

            # 提示: 这里抛出异常应该会在中间件触发之前
            # 不过我可以做这样一个假设：所有View对象都有标准的返回
            assert isinstance(resp, web_response.StreamResponse), \
                "Handler {!r} should return response instance, got {!r}".format(handler_name, type(resp),)
            return resp

        return wfunc

    def add_route(route_key, item, req_handler):
        cut_uri = lambda x: x[1:] if x and x[0] == '/' else x
        if type(item) == str:
            app.router.add_route(item, urljoin('/api', cut_uri(url), cut_uri(route_key)), wrap(req_handler))
        elif type(item) == dict:
            methods = item['method']
            if type(methods) == str:
                methods = [methods]
            elif type(methods) not in (list, set, tuple):
                raise BaseException('Invalid type of route config description: %s', type(item))

            for i in methods:
                if 'url' in item:
                    app.router.add_route(i, urljoin('/api', cut_uri(url), cut_uri(item['url'])), wrap(req_handler))
                else:
                    app.router.add_route(i, urljoin('/api', cut_uri(url), cut_uri(route_key)), wrap(req_handler))
        elif type(item) in (list, set, tuple):
            for i in item:
                add_route(route_key, i, req_handler)
        else:
            raise BaseException('Invalid type of route config description: %s', type(item))

    # noinspection PyProtectedMember
    for key, http_method in view_cls._interface.items():
        request_handler = getattr(view_cls, key, None)
        if request_handler: add_route(key, http_method, request_handler)


class Route:
    funcs = []
    views = []
    statics = []
    aiohttp_views = []

    def __init__(self):
        self.on_bind = []

    def __call__(self, url, method: [Iterable, str] = 'GET'):
        def _(obj):
            from .view import BasicView
            if iscoroutinefunction(obj):
                assert method, "Must give at least one method to http handler `%s`" % obj.__name__
                if type(method) == str: methods = (method,)
                else: methods = list(method)
                self.funcs.append((url, methods, obj))
            elif issubclass(obj, web.View):
                self.aiohttp_views.append((url, obj))
            elif issubclass(obj, BasicView):
                self.views.append((url, obj))
            else:
                raise BaseException('Invalid type for router')
            return obj
        return _

    def head(self, url):
        return self.__call__(url, 'HEAD')

    def get(self, url):
        return self.__call__(url, 'GET')

    def post(self, url):
        return self.__call__(url, 'POS')

    def put(self, url):
        return self.__call__(url, 'PUT')

    def patch(self, url):
        return self.__call__(url, 'PATCH')

    def delete(self, url):
        return self.__call__(url, 'DELETE')

    def add_static(self, prefix, path, **kwargs):
        """
        :param prefix: URL prefix
        :param path: file directory
        :param kwargs:
        :return:
        """
        self.statics.append((prefix, path, kwargs),)

    def bind(self, app):
        for url, cls in self.views:
            view_bind(app, url, cls)

        for url, cls in self.aiohttp_views:
            app.router.add_route('*', url, cls)

        for url, methods, func in self.funcs:
            for method in methods:
                app.router.add_route(method, url, func)

        for prefix, path, kwargs in self.statics:
            app.router.add_static(prefix, path, **kwargs)

        for func in self.on_bind:
            if iscoroutinefunction(func):
                async_run(func(app))
            elif callable(func):
                func(app)


def _value_encode(obj):
    return msgpack.dumps(obj, use_bin_type=True)


def _value_decode(data: bytes):
    return msgpack.loads(data, encoding='utf-8')


def _create_signature(secret: bytes, s):
    # hash = hashlib.blake2s(_signature_encode(s), key=secret[:32]) py3.6+
    m = hmac.new(secret, digestmod=hashlib.sha256)
    m.update(_value_encode(s))
    return m.hexdigest()


def create_signed_value(secret, s: [list, tuple]):
    sign = _create_signature(secret, s)
    return str(base64.b64encode(_value_encode(s + [sign])), 'utf-8')


def decode_signed_value(secret, s):
    s = _value_decode(base64.b64decode(bytes(s, 'utf-8')))
    data = s[:-1]
    sign = _create_signature(secret, data)
    if sign != s[-1]:
        return None
    return data
