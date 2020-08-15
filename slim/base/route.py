import inspect
import logging
import re
import time
from asyncio import iscoroutinefunction, Future
from types import FunctionType
from typing import Iterable, Type, TYPE_CHECKING, Dict, Callable, Awaitable, Any, List, Optional, Tuple
from posixpath import join as urljoin


from slim.base.types.doc import ResponseDataModel
from slim.base.types.route_meta_info import RouteViewInfo, RouteInterfaceInfo
# from slim.base.ws import WSRouter
from slim.exception import InvalidPostData, InvalidParams, InvalidRouteUrl
from slim.utils import get_class_full_name, camel_case_to_underscore_case, repath

if TYPE_CHECKING:
    from .view import BaseView
    from .app import Application

logger = logging.getLogger(__name__)
# __all__ = ('Route',)


class Route:
    _views: List[RouteViewInfo]

    def __init__(self, app):
        self._funcs = []
        self._views = []
        self.statics = []

        self._app = app
        self.before_bind = []
        self.after_bind = []  # on_bind(app)

        self._url_mappings: Dict[str, Dict[str, RouteInterfaceInfo]] = {}
        self.url_mappings_regex: Dict[str, Dict[re.Pattern, RouteInterfaceInfo]] = {}

    def interface(self, method, url=None, *, summary=None, va_query=None, va_post=None, va_headers=None,
                  va_resp=ResponseDataModel, deprecated=False):
        """
        Register interface
        :param method:
        :param url:
        :param summary:
        :param va_query:
        :param va_post:
        :param va_headers:
        :param va_resp:
        :param deprecated:
        :return:
        """
        def wrapper(func: FunctionType):
            self._funcs.append(func)
            arg_spec = inspect.getfullargspec(func)

            names_exclude = set()
            names_include = set()
            names_varkw = arg_spec.varkw

            if len(arg_spec.args) >= 1:
                # skip the first argument, the view instance
                names_exclude.add(arg_spec.args[0])
                for i in arg_spec.args[1:]:
                    names_include.add(i)

            for i in arg_spec.kwonlyargs:
                names_include.add(i)

            func._route_info = RouteInterfaceInfo(
                method,
                url or func.__name__,
                func,
                summary=summary,
                va_query=va_query,
                va_post=va_post,
                va_headers=va_headers,
                va_resp=va_resp,
                deprecated=deprecated,

                names_exclude=names_exclude,
                names_include=names_include,
                names_varkw=names_varkw
            )
            return func
        return wrapper

    def view(self, url, tag_name=None):
        """
        Register View Class
        :param url:
        :param tag_name:
        :return:
        """
        from .view import BaseView

        def wrapper(view_cls):
            if issubclass(view_cls, BaseView):
                view_url = url if url else camel_case_to_underscore_case(view_cls.__name__)
                route_info = RouteViewInfo(view_url, view_cls, tag_name)
                view_cls._route_info = route_info
                self._views.append(route_info)
            return view_cls

        return wrapper

    def _bind(self):
        from ._view.base_view import ViewRequest

        def add_to_url_mapping(_meta, _fullpath):
            if ':' not in _fullpath and '(' not in _fullpath:
                self._url_mappings.setdefault(_meta.method, {})
                self._url_mappings[_meta.method][_fullpath] = _meta
            else:
                self.url_mappings_regex.setdefault(_meta.method, {})
                try:
                    _re = repath.pattern(_fullpath)
                    self.url_mappings_regex[_meta.method][re.compile(_re)] = _meta
                except Exception as e:
                    raise InvalidRouteUrl(_fullpath, e)

        # bind views
        for view_info in self._views:
            view_cls = view_info.view_cls
            view_cls._on_bind(self)

            for k, v in vars(view_cls).items():
                if isinstance(v, FunctionType):
                    # bind interface to url mapping
                    if getattr(v, '_route_info', None):
                        meta: RouteInterfaceInfo = v._route_info
                        meta.view_cls = view_cls
                        meta.handler_name = '%s.%s' % (get_class_full_name(view_cls), meta.handler.__name__)

                        fullpath = urljoin(self._app.mountpoint, view_info.url, meta.url)
                        add_to_url_mapping(meta, fullpath)

        # bind functions
        for i in self._funcs:
            if not i._route_info.view_cls:
                meta: RouteInterfaceInfo = i._route_info
                meta.view_cls = ViewRequest
                meta.handler_name = meta.handler.__name__
                meta.is_free_func = True

                fullpath = urljoin(self._app.mountpoint, meta.url)
                add_to_url_mapping(meta, fullpath)

    def query_path(self, method, path) -> Tuple[Optional[RouteInterfaceInfo], Optional[Dict]]:
        """
        Get route info for specified method and path.
        :param method:
        :param path:
        :return:
        """
        path_mapping = self._url_mappings.get(method, None)
        if path_mapping:
            ret = path_mapping.get(path)
            if ret:
                return ret, {}

        path_mapping = self.url_mappings_regex.get(method, None)
        if path_mapping:
            for i, route_info in path_mapping.items():
                m = i.fullmatch(path)
                if m:
                    call_kwargs = m.groupdict()
                    if route_info.names_varkw is not None:
                        for j in route_info.names_exclude:
                            del call_kwargs[j]

                    for j in call_kwargs.keys() - route_info.names_include:
                        del call_kwargs[j]

                    return route_info, call_kwargs

        return None, None

    def websocket(self, url, obj):
        """
        Register Websocket
        :param url:
        :param obj:
        :return:
        """
        def wrapper(cls):
            if issubclass(cls, WSRouter):
                self.websockets.append((url, obj()))
            return cls

        return wrapper

    def add_static(self, prefix, path, **kwargs):
        """
        :param prefix: URL prefix
        :param path: file directory
        :param kwargs:
        :return:
        """
        self.statics.append((prefix, path, kwargs),)

    # alias function

    def get(self, url=None, *, summary=None, va_query=None, va_post=None, va_headers=None,
                  va_resp=ResponseDataModel, deprecated=False):
        kwargs = locals()
        del kwargs['self']
        return self.interface('GET', **kwargs)

    def post(self, url=None, *, summary=None, va_query=None, va_post=None, va_headers=None,
                  va_resp=ResponseDataModel, deprecated=False):
        kwargs = locals()
        del kwargs['self']
        return self.interface('GET', **kwargs)
