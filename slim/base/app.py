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
    def __init__(self, *, cookies_secret: bytes, enable_log=True, session_cls=CookieSession):
        from .route import get_route_middleware, Route

        self.route = Route(self)
        self.tables = SlimTables()
        self.permissions = SlimPermissions()

        if enable_log:
            log.enable()

        self.options = ApplicationOptions()
        self.options.cookies_secret = cookies_secret
        self.options.session_cls = session_cls
        self._raw_app = web.Application(middlewares=[get_route_middleware(self)])

    def run(self, host, port):
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

        web.run_app(host=host, port=port, app=self._raw_app)
