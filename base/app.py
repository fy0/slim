import asyncio
from aiohttp import web
from aiohttp_session import setup as session_setup, SimpleCookieStorage
from aiohttp_session import Session, AbstractStorage
from . import log


class SecureCookieStorage(AbstractStorage):
    """Encrypted JSON storage.
    """

    def __init__(self, secret_key: bytes, *, cookie_name="s",
                 domain=None, max_age=None, path='/',
                 secure=None, httponly=True):
        super().__init__(cookie_name=cookie_name, domain=domain,
                         max_age=max_age, path=path, secure=secure,
                         httponly=httponly)

        self.secret_key = secret_key

    @asyncio.coroutine
    def load_session(self, request):
        cookie = self.load_cookie(request)
        if cookie is None:
            return Session(None, data=None, new=True, max_age=self.max_age)
        else:
            try:
                data = json.loads(
                    self._fernet.decrypt(
                        cookie.encode('utf-8')).decode('utf-8'))
                return Session(None, data=data,
                               new=False, max_age=self.max_age)
            except InvalidToken:
                log.warning("Cannot decrypt cookie value, "
                            "create a new fresh session")
                return Session(None, data=None, new=True, max_age=self.max_age)

    @asyncio.coroutine
    def save_session(self, request, response, session):
        if session.empty:
            return self.save_cookie(response, '',
                                    max_age=session.max_age)

        cookie_data = json.dumps(
            self._get_session_data(session)
        ).encode('utf-8')
        self.save_cookie(
            response,
            self._fernet.encrypt(cookie_data).decode('utf-8'),
            max_age=session.max_age
        )


def app_init(default=None, *, cookies_secret: bytes, enable_log=True, route=None) -> web.Application:
    if isinstance(default, dict):
        app = web.Application(**default)
    elif isinstance(default, web.Application):
        app = default
    else:
        app = web.Application()

    app._info_for_mapi = {
        'cookies_secret': cookies_secret
    }

    if enable_log:
        log.enable()

    if route:
        # 推后至启动时进行
        def on_available(app):
            route.bind(app)
        app.on_loop_available.append(on_available)

    session_setup(app, SimpleCookieStorage())
    #session_setup(app, SecureCookieStorage(secret_key=cookies_secret))
    return app
