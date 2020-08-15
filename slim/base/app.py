import logging
import asyncio
import time
from typing import Union, List, Optional, TYPE_CHECKING, Iterable, Callable, Awaitable, Dict

from slim.base.types.doc import ApplicationDocInfo
from slim.ext.decorator import deprecated
# from slim.ext.openapi.serve import doc_serve
from .session import CookieSession
from ..utils import get_ioloop
from ..utils.jsdict import JsDict
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
                 permission: Optional['Permissions'] = None, client_max_size=100 * 1024 * 1024,
                 cors_options: Optional[CORSOptions] = None):
        """
        :param cookies_secret:
        :param log_level:
        :param permission: `ALL_PERMISSION`, `EMPTY_PERMISSION` or a `Permissions` object
        :param session_cls:
        :param mountpoint:
        :param doc_enable:
        :param doc_info:
        :param client_max_size: 100MB
        """
        from .route import Route
        from .permission import Permissions, Ability, ALL_PERMISSION, EMPTY_PERMISSION

        self.on_startup = []
        self.on_shutdown = []
        self.on_cleanup = []

        self.mountpoint = mountpoint
        self.route = Route(self)
        self.doc_enable = doc_enable
        self.doc_info = doc_info

        if self.doc_enable:
            # doc_serve(self)
            pass

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
        self.client_max_size = client_max_size

    def prepare(self):
        from .view import AbstractSQLView
        self.route._bind()
        return

        for vi in self.route._views:
            cls = vi.view_cls
            if issubclass(cls, AbstractSQLView):
                '''
                def get_exists_view_full_name():
                    view_cls = self.tables[cls.table_name]
                    return '%s.%s' % (view_cls.__module__, view_cls.__name__)

                def get_view_full_name():
                    return '%s.%s' % (cls.__module__, cls.__name__)

                if cls.table_name in self.tables:
                    logger.error("Binding %r failed, the table %r is already binded to %r." % (get_view_full_name(), cls.table_name, get_exists_view_full_name()))
                    exit(-1)
                '''

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
                    try:
                        cors.add(r)
                    except ValueError:
                        pass

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await self.prepare()
                    await send({'type': 'lifespan.startup.complete'})

                elif message['type'] == 'lifespan.shutdown':
                    await send({'type': 'lifespan.shutdown.complete'})
                    return

        if scope['type'] == 'http':
            route_info, call_kwargs_raw = self.route.query_path(scope['method'], scope['path'])

            if route_info:
                t = time.perf_counter()

                # filter call_kwargs
                call_kwargs = call_kwargs_raw.copy()
                if route_info.names_varkw is not None:
                    for j in route_info.names_exclude:
                        del call_kwargs[j]

                for j in call_kwargs.keys() - route_info.names_include:
                    del call_kwargs[j]

                # build a view instance
                view = await route_info.view_cls._assemble(self, scope, receive, send)
                view._route_info = call_kwargs

                # make the method bounded
                handler = route_info.handler.__get__(view)

                # note: view.prepare() may case finished
                if not view.is_finished:
                    # user's validator check
                    from slim.base._view.validate import view_validate_check
                    await view_validate_check(view, route_info.va_query, route_info.va_post, route_info.va_headers)

                    if not view.is_finished:
                        # call the request handler
                        if asyncio.iscoroutinefunction(handler):
                            await handler(**call_kwargs)
                        else:
                            handler(**call_kwargs)

                took = round((time.perf_counter() - t) * 1000, 2)
                # GET /api/get -> TopicView.get 200 30ms
                # logger.info("{} {:4s} -> {} {}, took {}ms".format(method, ascii_encodable_path, handler_name, status_code, took))

                # if status_code == 500:
                #     warn_text = "The handler {!r} did not called `view.finish()`.".format(handler_name)
                #     logger.warning(warn_text)
                #     view_instance.finish_raw(warn_text.encode('utf-8'), status=500)
                #     return resp
                #
                # await view_instance._on_finish()

                if view.response:
                    resp = view.response
                    await send({
                        'type': 'http.response.start',
                        'status': resp.status,
                        'headers': resp.build_headers()
                    })

                await send({
                    'type': 'http.response.body',
                    'body': await resp.get_body(),
                })
                return

            await send({
                'type': 'http.response.start',
                'status': 404,
                'headers': [
                    [b'content-type', b'text/plain'],
                ]
            })

            await send({
                'type': 'http.response.body',
                'body': b'not found',
            })

    def run(self, host, port):
        import uvicorn
        uvicorn.run(self, host=host, port=port, log_level='info')
