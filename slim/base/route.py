import logging
from asyncio import iscoroutinefunction, Future
from typing import Iterable, Type, TYPE_CHECKING, Dict
from aiohttp import web, web_response
from posixpath import join as urljoin

from aiohttp.abc import Request
from schematics.exceptions import DataError

from slim.base._view.validate import view_validate_check
from slim.base.types.beacon import BeaconInfo, BeaconRouteInfo
from slim.base.ws import WSRouter
from slim.exception import InvalidPostData, InvalidParams
from slim.utils import get_class_full_name
from ..utils.async_run import sync_call, async_call

if TYPE_CHECKING:
    from .view import BaseView
    from .app import Application

logger = logging.getLogger(__name__)
# __all__ = ('Route',)


def get_route_middleware(app: 'Application'):
    @web.middleware
    # noinspection PyProtectedMember
    async def route_middleware(request: Request, handler):
        if not app.route._is_beacon(handler):
            return await handler(request)
        else:
            beacon = app.route._beacons[handler]
            handler_name = beacon.handler_name

            ascii_encodable_path = request.path_qs.encode('ascii', 'backslashreplace').decode('ascii')
            status_code = 200

            view_instance: BaseView = beacon.view_cls(app, request)
            method = view_instance.method

            from .view import ErrorCatchContext

            with ErrorCatchContext(view_instance):
                await view_instance._prepare()

            if view_instance.is_finished:
                resp = view_instance.response
            else:
                # user's validator check
                await view_validate_check(view_instance, beacon.va_query, beacon.va_post)

                if view_instance.is_finished:
                    resp = view_instance.response
                else:
                    # handle request
                    await beacon.handler(view_instance)

                    # get response
                    resp = view_instance.response

                    if not isinstance(resp, web_response.StreamResponse):
                        status_code = 500

            # GET /api/get -> TopicView.get 200
            logger.info("{} {:4s} -> {} {}".format(method, ascii_encodable_path, handler_name, status_code))

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('query parameters: %s', view_instance.params)
                logger.debug('post data: %s', await view_instance.post_data())

            if status_code == 500:
                resp.set_status(status_code, "The handler {!r} did not called `view.finish()`.".format(handler_name))
                return resp

            await view_instance._on_finish()
            return resp

    return route_middleware


def view_bind(app: 'Application', cls_url, view_cls: Type['BaseView']):
    """
    将 API 绑定到 web 服务上
    :param view_cls:
    :param app:
    :param cls_url:
    :return:
    """
    if view_cls._no_route: return
    cls_url = cls_url or view_cls.__class__.__name__.lower()

    def add_route(beacon_info: BeaconInfo):
        route = beacon_info['route']
        for method in route['method']:
            async def beacon(request): pass
            app._raw_app.router.add_route(method, route['fullpath'], beacon)
            app.route._beacons[beacon] = beacon_info

    # noinspection PyProtectedMember
    for name, route_info_lst in view_cls._interface.items():
        for route_info in route_info_lst:
            real_handler = getattr(view_cls, name, None)
            if real_handler is None: continue  # TODO: delete
            assert real_handler is not None, "handler must be exists"

            handler_name = '%s.%s' % (get_class_full_name(view_cls), name or real_handler.__name__)
            if not iscoroutinefunction(real_handler):
                logger.error("Interface function must be async: %r" % handler_name)
                exit(-1)

            cls_url = cls_url or view_cls.__class__.__name__.lower()
            route_key = route_info['url'] or name

            beacon_info = BeaconInfo({
                'view_cls': view_cls,
                'name': name,  # name of function
                'handler': real_handler,
                'handler_name': handler_name,  # qualified name
                'route': BeaconRouteInfo({
                    'method': route_info['method'],  # Set[HttpMethod]
                    'relpath': route_key,
                    'fullpath': urljoin(app.mountpoint, cls_url, route_key),
                    'raw': route_info
                }),
                'va_query': route_info.get('va_query'),
                'va_post': route_info.get('va_post')
            })

            add_route(beacon_info)


class Route:
    _beacons: Dict[Future, BeaconInfo]

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
    def interface(method, url=None, *, summary=None, va_query=None, va_post=None):  # va_header, etc.
        def wrapper(func):
            meta = {
                'summary': summary,
                'va_query': va_query,
                'va_post': va_post
            }
            func._interface = (method, url, meta)
            return func
        return wrapper

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
