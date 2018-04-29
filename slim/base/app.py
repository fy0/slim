import logging
import asyncio
from aiohttp import web
from aiohttp.web_urldispatcher import StaticResource
from slim.utils.jsdict import JsDict
from .session import CookieSession
import aiohttp_cors
from . import log


class SlimTables(JsDict):
    # key: table_name
    # value: SQLView
    def __repr__(self):
        return '<SlimTables ' + dict.__repr__(self) + '>'


class SlimPermissions(JsDict):
    def __repr__(self):
        return '<SlimPermissions ' + dict.__repr__(self) + '>'


class ApplicationOptions:
    def __init__(self):
        self.cookies_secret = b'use a secret'
        self.session_cls = CookieSession


class Application:
    def __init__(self, *, cookies_secret: bytes, log_level=logging.DEBUG, session_cls=CookieSession,
                 client_max_size=2*1024*1024):
        """
        :param cookies_secret:
        :param log_level:
        :param session_cls:
        :param client_max_size: 2MB is default client_max_body_size of nginx
        """
        from .route import get_route_middleware, Route

        self.route = Route(self)
        self.tables = SlimTables()
        self.permissions = SlimPermissions()

        if log_level:
            log.enable(log_level)

        self.options = ApplicationOptions()
        self.options.cookies_secret = cookies_secret
        self.options.session_cls = session_cls
        self._raw_app = web.Application(middlewares=[get_route_middleware(self)], client_max_size=client_max_size)

    def _prepare(self):
        from .view import AbstractSQLView
        self.route.bind()

        for _, cls in self.route.views:
            if issubclass(cls, AbstractSQLView):
                self.tables[cls.table_name] = cls
                self.permissions[cls.table_name] = cls.permission
                cls.permission.app = self

        # Configure default CORS settings.
        cors = aiohttp_cors.setup(self._raw_app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })

        # Configure CORS on all routes.
        ws_set = set()
        for url, wsh in self.route.websockets:
            ws_set.add(wsh._handle)

        for r in list(self._raw_app.router.routes()):
            if type(r.resource) != StaticResource and r.handler not in ws_set:
                cors.add(r)

        for _, cls in self.route.views:
            cls._ready()

    def run(self, host, port):
        self._prepare()
        web.run_app(host=host, port=port, app=self._raw_app)

    def timer(self, interval_seconds, *, exit_when):
        loop = asyncio.get_event_loop()

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
