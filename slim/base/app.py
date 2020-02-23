import logging
import asyncio
from typing import Union, List, Optional, TYPE_CHECKING, Iterable
from aiohttp import web
from aiohttp.web_urldispatcher import StaticResource

from slim.base.types.doc import ApplicationDocInfo
from slim.ext.openapi.serve import doc_serve
from .session import CookieSession
from ..utils import get_ioloop
from ..utils.jsdict import JsDict
import aiohttp_cors
from . import log

if TYPE_CHECKING:
    from .permission import Permissions

logger = logging.getLogger(__name__)


class SlimTables(JsDict):
    # key: table_name
    # value: SQLView
    def __repr__(self):
        return '<SlimTables ' + dict.__repr__(self) + '>'


class ApplicationOptions:
    def __init__(self):
        self.cookies_secret = b'use a secret'
        self.session_cls = CookieSession


class CORSOptions:
    def __init__(self, host, *, allow_credentials=False, expose_headers=(),
                 allow_headers=(), max_age=None, allow_methods=None):
        self.host = host
        self.allow_credentials = allow_credentials
        self.expose_headers = expose_headers
        self.allow_headers = allow_headers
        self.max_age = max_age
        self.allow_methods = allow_methods


class Application:
    def __init__(self, *, cookies_secret: bytes, log_level=logging.INFO, session_cls=CookieSession,
                 mountpoint: str = '/api', doc_enable=True, doc_info=ApplicationDocInfo(),
                 permission: Optional['Permissions'] = None, client_max_size=2 * 1024 * 1024,
                 cors_options: Optional[Union[CORSOptions, List[CORSOptions]]] = None):
        """
        :param cookies_secret:
        :param log_level:
        :param permission: `ALL_PERMISSION`, `EMPTY_PERMISSION` or a `Permissions` object
        :param session_cls:
        :param mountpoint:
        :param doc_enable:
        :param doc_info:
        :param client_max_size: 2MB is default client_max_body_size of nginx
        """
        from .route import get_route_middleware, Route
        from .permission import Permissions, Ability, ALL_PERMISSION, EMPTY_PERMISSION

        self.on_startup = []
        self.on_shutdown = []
        self.on_cleanup = []

        self.mountpoint = mountpoint
        self.route = Route(self)
        self.doc_enable = doc_enable
        self.doc_info = doc_info

        if self.doc_enable:
            doc_serve(self)

        if permission is ALL_PERMISSION:
            logger.warning('app.permission is ALL_PERMISSION, it means everyone has all permissions for any table')
            logger.warning("This option should only be used in development environment")
            self.permission = Permissions(self)
            self.permission.add(None, Ability({'*': '*'}))  # everyone has all permission for all table
        elif permission is None or permission is EMPTY_PERMISSION:
            self.permission = Permissions(self)  # empty
        else:
            self.permission = permission
            permission.app = self

        self.tables = SlimTables()

        if log_level:
            log.enable(log_level)

        if isinstance(cors_options, CORSOptions):
            self.cors_options = [cors_options]
        else:
            self.cors_options = cors_options

        self.options = ApplicationOptions()
        self.options.cookies_secret = cookies_secret
        self.options.session_cls = session_cls
        self._raw_app = web.Application(middlewares=[get_route_middleware(self)], client_max_size=client_max_size)

    def _prepare(self):
        from .view import AbstractSQLView
        self.route.bind()

        for _, cls in self.route.views:
            if issubclass(cls, AbstractSQLView):
                def get_exists_view_full_name():
                    view_cls = self.tables[cls.table_name]
                    return '%s.%s' % (view_cls.__module__, view_cls.__name__)

                if cls.table_name in self.tables:
                    logger.error("The table (%r) is already binded to %r." % (cls.table_name, get_exists_view_full_name()))
                    exit(-1)

                self.tables[cls.table_name] = cls

        # Configure default CORS settings.
        if self.cors_options:
            vals = {}
            for i in self.cors_options:
                vals[i.host] = aiohttp_cors.ResourceOptions(
                    allow_credentials=i.allow_credentials,
                    expose_headers=i.expose_headers,
                    allow_headers=i.allow_headers,
                    max_age=i.max_age,
                    allow_methods=i.allow_methods
                )
            cors = aiohttp_cors.setup(self._raw_app, defaults=vals)
        else:
            cors = None

        # Configure CORS on all routes.
        ws_set = set()
        for url, wsh in self.route.websockets:
            ws_set.add(wsh._handle)

        if cors:
            for r in list(self._raw_app.router.routes()):
                if type(r.resource) != StaticResource and r.handler not in ws_set:
                    cors.add(r)

        for _, cls in self.route.views:
            cls._ready()

    def run(self, host, port):
        def reg(mine, target):
            assert isinstance(mine, Iterable)

            for i in mine:
                assert i, asyncio.Future

                async def dummy(_raw_app):
                    await i()
                target.append(dummy)

        reg(self.on_startup, self._raw_app.on_startup)
        reg(self.on_shutdown, self._raw_app.on_shutdown)
        reg(self.on_cleanup, self._raw_app.on_cleanup)

        self._prepare()
        web.run_app(host=host, port=port, app=self._raw_app)

    @staticmethod
    def timer(interval_seconds, *, exit_when):
        """
        Set up a timer
        :param interval_seconds:
        :param exit_when:
        :return:
        """
        loop = get_ioloop()

        def wrapper(func):
            def runner():
                if exit_when and exit_when():
                    return

                loop.call_later(interval_seconds, runner)

                if asyncio.iscoroutinefunction(func):
                    asyncio.ensure_future(func())
                else:
                    func()

            loop.call_later(interval_seconds, runner)
            return func

        return wrapper
