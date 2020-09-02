import logging
from typing import Optional, TYPE_CHECKING, Type

from slim.base.types.doc import ApplicationDocInfo
from slim.ext.openapi.serve import doc_serve
from .session import CookieSession
from .user import BaseUserViewMixin
from .web import handle_request, CORSOptions
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
        self.cookies_secret = b'secret code'
        self.session_cls = CookieSession


class Application:
    def __init__(self, *, cookies_secret: bytes = b'secret code', log_level=logging.INFO, session_cls=CookieSession,
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

        self.user_mixin_class = None
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
        self.client_max_size = client_max_size
        self._last_view = None  # use for tests
        self._last_resp = None  # use for tests

    def prepare(self):
        self.route._bind()

    async def __call__(self, scope, receive, send, *, raise_for_resp=False):
        await handle_request(self, scope, receive, send, raise_for_resp=raise_for_resp)

    def set_user_mixin_class(self, cls: Type[BaseUserViewMixin]):
        self.user_mixin_class = cls

    def run(self, host, port):
        import uvicorn
        logger.info(f'Running on http://{host}:{port}')
        logger.info('(Press CTRL+C to quit)')
        uvicorn.run(self, host=host, port=port, log_level='error')
