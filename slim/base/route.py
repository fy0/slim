import inspect
import logging
import os
import re
from types import FunctionType
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union
from posixpath import join as urljoin

from slim.base.types.doc import ResponseDataModel
from slim.base.types.route_meta_info import RouteViewInfo, RouteInterfaceInfo, RouteStaticsInfo, RouteWebsocketInfo
from slim.exception import InvalidRouteUrl, StaticDirectoryNotExists
from slim.base.web.staticfile import StaticFileResponder
from slim.utils import get_class_full_name, camel_case_to_underscore_case, repath, sentinel
from slim.base.web.ws import WebSocket

if TYPE_CHECKING:
    from .view import BaseView

logger = logging.getLogger(__name__)


# __all__ = ('Route',)


class Route:
    _views: List[RouteViewInfo]

    def __init__(self, app):
        self._funcs = []
        self._views = []
        self._funcs_meta = []
        self._statics = []
        self._websockets = []

        self._app = app
        self.before_bind = []
        self.after_bind = []  # on_bind(app)

        self._url_mappings: Dict[str, Dict[str, RouteInterfaceInfo]] = {}
        self._url_mappings_regex: Dict[str, Dict[re.Pattern, RouteInterfaceInfo]] = {}
        self._url_ws_mappings: Dict[str, RouteWebsocketInfo] = {}
        self._url_ws_mappings_regex: Dict[re.Pattern, RouteWebsocketInfo] = {}
        self._statics_mappings_regex: Dict[str, Dict[re.Pattern, RouteStaticsInfo]] = {}

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
                # skip the first argument, the sqlview instance
                names_exclude.add(arg_spec.args[0])
                for i in arg_spec.args[1:]:
                    names_include.add(i)

            for i in arg_spec.kwonlyargs:
                names_include.add(i)

            func._route_info = RouteInterfaceInfo(
                [method],
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
        from .view.base_view import BaseView

        def wrapper(view_cls):
            assert inspect.isclass(view_cls), '%r is not a class' % view_cls.__name__
            if issubclass(view_cls, BaseView):
                view_url = url if url else camel_case_to_underscore_case(view_cls.__name__)
                route_info = RouteViewInfo(view_url, view_cls, tag_name)
                view_cls._route_info = route_info
                self._views.append(route_info)
            else:
                raise Exception('%r is not a View class compatible with slim' % view_cls.__name__)
            return view_cls

        return wrapper

    def _bind(self):
        from .view.request_view import RequestView

        def add_to_url_mapping(_meta, _fullpath):
            um = self._url_mappings
            um_re = self._url_mappings_regex

            for method in _meta.methods:
                if ':' not in _fullpath and '(' not in _fullpath:
                    um.setdefault(method, {})
                    um[method][_fullpath] = _meta
                else:
                    um_re.setdefault(method, {})
                    try:
                        _re = repath.pattern(_fullpath)
                        um_re[method][re.compile(_re)] = _meta
                    except Exception as e:
                        raise InvalidRouteUrl(_fullpath, e)

        def add_to_url_ws_mapping(_meta, _fullpath):
            if ':' not in _fullpath and '(' not in _fullpath:
                self._url_ws_mappings[_fullpath] = _meta
            else:
                try:
                    _re = repath.pattern(_fullpath)
                    self._url_ws_mappings_regex[re.compile(_re)] = _meta
                except Exception as e:
                    raise InvalidRouteUrl(_fullpath, e)

        # bind views
        for view_info in self._views:
            view_cls = view_info.view_cls
            view_cls._on_bind(self)

            for k, v in inspect.getmembers(view_cls):
                if isinstance(v, FunctionType):
                    # bind interface to url mapping
                    if getattr(v, '_route_info', None):
                        meta: RouteInterfaceInfo = v._route_info
                        meta.view_cls = sentinel  # just a flag
                        meta.view_cls_set.add(view_cls)

                        meta = meta.clone()  # make clone because interface could be inherit.
                        meta.view_cls = view_cls
                        meta.handler_name = '%s.%s' % (get_class_full_name(view_cls), meta.handler.__name__)

                        fullpath = urljoin(self._app.mountpoint, view_info.url, meta.url)
                        meta.fullpath = fullpath
                        add_to_url_mapping(meta, fullpath)
                        self._funcs_meta.append(meta)

            # if issubclass(view_cls, AbstractSQLView):
            #     self._app.tables[view_cls.table_name] = view_cls

        # bind functions
        for i in self._funcs:
            if not i._route_info.view_cls:
                meta: RouteInterfaceInfo = i._route_info
                meta.view_cls = RequestView
                meta.handler_name = meta.handler.__name__
                meta.is_free_func = True

                fullpath = urljoin(self._app.mountpoint, meta.url)
                meta.fullpath = fullpath
                add_to_url_mapping(meta, fullpath)
                self._funcs_meta.append(meta)

        # bind statics
        for meta in self._statics:
            meta: RouteStaticsInfo
            fullpath = urljoin(self._app.mountpoint, meta.url)
            meta.fullpath = fullpath
            meta.responder = StaticFileResponder(fullpath, meta.static_path)
            add_to_url_mapping(meta, fullpath)

        # bind websockets
        for meta in self._websockets:
            meta: RouteWebsocketInfo

            fullpath = urljoin(self._app.mountpoint, meta.url)
            meta.fullpath = fullpath
            add_to_url_ws_mapping(meta, fullpath)

    def query_ws_path(self, path) -> Tuple[Union[RouteWebsocketInfo, None], Optional[Dict]]:
        ret = self._url_ws_mappings.get(path)
        if ret:
            return ret, {}

        for i, route_info in self._url_ws_mappings_regex.items():
            m = i.fullmatch(path)
            if m:
                if isinstance(route_info, RouteWebsocketInfo):
                    return route_info, m.groupdict()

        return None, None

    def query_path(self, method, path) -> Tuple[Union[RouteInterfaceInfo, RouteStaticsInfo, None], Optional[Dict]]:
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
                if ret.handler.__name__ not in ret.view_cls._interface_disable:
                    return ret, {}

        path_mapping = self._url_mappings_regex.get(method, None)
        if path_mapping:
            for i, route_info in path_mapping.items():
                m = i.fullmatch(path)
                if m:
                    if isinstance(route_info, RouteStaticsInfo):
                        return route_info, m.groupdict()
                    if route_info.handler.__name__ not in route_info.view_cls._interface_disable:
                        return route_info, m.groupdict()

        return None, None

    def websocket(self, url=None):
        """
        Register Websocket
        :param url:
        :return:
        """
        def wrapper(cls):
            if issubclass(cls, WebSocket):
                if url is None:
                    url2 = camel_case_to_underscore_case(cls.__name__)
                else:
                    url2 = url
                self._websockets.append(RouteWebsocketInfo(url2, cls))
            return cls

        return wrapper

    def add_static(self, url_prefix: str, static_path: str):
        """
        :param url_prefix: URL prefix
        :param static_path: file directory
        :param kwargs:
        :return:
        """
        if not ':file' in url_prefix:
            if url_prefix.endswith('/'):
                url_prefix += '/'
            url_prefix += ':file(.+)'

        if not os.path.exists(static_path):
            raise StaticDirectoryNotExists(static_path)

        self._statics.append(RouteStaticsInfo(['GET'], url_prefix, static_path))

    def get(self, url=None, *, summary=None, va_query=None, va_post=None, va_headers=None,
            va_resp=ResponseDataModel, deprecated=False):
        kwargs = locals()
        del kwargs['self']
        return self.interface('GET', **kwargs)

    def post(self, url=None, *, summary=None, va_query=None, va_post=None, va_headers=None,
             va_resp=ResponseDataModel, deprecated=False):
        kwargs = locals()
        del kwargs['self']
        return self.interface('POST', **kwargs)
