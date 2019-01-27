import logging
from asyncio import iscoroutinefunction, Future
from typing import Iterable, Type, TYPE_CHECKING
from aiohttp import web, web_response
from posixpath import join as urljoin
from slim.base.ws import WSRouter
from ..utils.async_run import sync_call, async_call

if TYPE_CHECKING:
    from .view import BaseView

logger = logging.getLogger(__name__)
# __all__ = ('Route',)


def get_route_middleware(app):
    @web.middleware
    # noinspection PyProtectedMember
    async def route_middleware(request, handler):
        if not app.route._is_beacon(handler):
            return await handler(request)
        else:
            data = app.route._beacons[handler]
            view_cls = data['view']
            func = data['handler']

            view_instance = view_cls(app, request)
            handler_name = '%s.%s' % (view_cls.__name__, func.__name__)
            ascii_encodable_path = request.path.encode('ascii', 'backslashreplace').decode('ascii')
            logger.info("{} {} -> {}".format(request._method, ascii_encodable_path, handler_name))

            from .view import ErrorCatchContext

            with ErrorCatchContext(view_instance):
                await view_instance._prepare()
            if view_instance.is_finished:
                return view_instance.response

            with ErrorCatchContext(view_instance):
                await async_call(view_instance.prepare)
            if view_instance.is_finished:
                return view_instance.response

            resp = await func(view_instance) or view_instance.response
            assert isinstance(resp, web_response.StreamResponse), \
                "Handler {!r} should return response instance, got {!r}. Is view.finish() not be called?".format(handler_name, type(resp), )

            await view_instance._on_finish()
            await async_call(view_instance.on_finish)
            return resp

    return route_middleware


def view_bind(app, cls_url, view_cls: Type['BaseView']):
    """
    将 API 绑定到 web 服务上
    :param view_cls:
    :param app:
    :param cls_url:
    :return:
    """
    if view_cls._no_route: return
    cls_url = cls_url or view_cls.__class__.__name__.lower()

    def add_route(name, route_info, beacon_info):
        for method in route_info['method']:
            async def beacon(request): pass
            route_key = route_info['url'] if route_info['url'] else name
            app._raw_app.router.add_route(method, urljoin('/api', cls_url, route_key), beacon)
            app.route._beacons[beacon] = beacon_info

    # noinspection PyProtectedMember
    for name, route_info_lst in view_cls._interface.items():
        for route_info in route_info_lst:
            real_handler = getattr(view_cls, name, None)
            if real_handler is None: continue # TODO: delete
            assert real_handler is not None, "handler must be exists"

            handler_name = '%s.%s' % (view_cls.__name__, real_handler.__name__)
            assert iscoroutinefunction(real_handler), "Add 'async' before interface function %r" % handler_name

            beacon_info = {
                'view': view_cls,
                'name': name,
                'handler': real_handler,
                'route_info': route_info
            }
            add_route(name, route_info, beacon_info)


class Route:
    def __init__(self, app):
        self.funcs = []
        self.views = []
        self.statics = []
        self.aiohttp_views = []
        self.websockets = []

        self.app = app
        self.before_bind = []
        self.after_bind = []  # on_bind(app)
        self._beacons = {}

    @staticmethod
    def interface(method, url=None):
        def wrapper(func):
            func._interface = (method, url)
            return func
        return wrapper

    @staticmethod
    def discard(name, method='ALL'):
        pass

    def _is_beacon(self, func):
        return func in self._beacons

    def __call__(self, url, method: [Iterable, str, None] = 'GET'):
        def _(obj):
            from .view import BaseView
            if iscoroutinefunction(obj):
                assert method, "Must give at least one method to http handler `%s`" % obj.__name__
                if type(method) == str: methods = (method,)
                else: methods = list(method)
                self.funcs.append((url, methods, obj))
            elif isinstance(obj, type):
                if issubclass(obj, WSRouter):
                    self.websockets.append((url, obj()))
                elif issubclass(obj, web.View):
                    self.aiohttp_views.append((url, obj))
                elif issubclass(obj, BaseView):
                    if method is None:
                        # internal view, can't request over http
                        obj._no_route = True
                    self.views.append((url, obj))
                else:
                    raise BaseException('Invalid type for router: %r' % type(obj).__name__)
            else:
                raise BaseException('Invalid type for router: %r' % type(obj).__name__)
            return obj
        return _

    def add_static(self, prefix, path, **kwargs):
        """
        :param prefix: URL prefix
        :param path: file directory
        :param kwargs:
        :return:
        """
        self.statics.append((prefix, path, kwargs),)

    def bind(self):
        app = self.app
        raw_router = app._raw_app.router

        for func in self.before_bind:
            sync_call(func, app)

        for url, cls in self.views:
            view_bind(app, url, cls)

        for url, wsh in self.websockets:
            raw_router.add_get(url, wsh._handle)

        for url, cls in self.aiohttp_views:
            raw_router.add_route('*', url, cls)

        for url, methods, func in self.funcs:
            for method in methods:
                raw_router.add_route(method, url, func)

        for prefix, path, kwargs in self.statics:
            raw_router.add_static(prefix, path, **kwargs)

        for func in self.after_bind:
            sync_call(func, app)
