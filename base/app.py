import asyncio
from aiohttp import web
from .session import SimpleSession
from . import log


class SlimApplicationOptions:
    def __init__(self):
        self.cookies_secret = b'use a secret'
        self.session_cls = SimpleSession


def app_init(default=None, *, cookies_secret: bytes, enable_log=True, route=None, session_cls=SimpleSession) -> web.Application:
    if isinstance(default, dict):
        app = web.Application(**default)
    elif isinstance(default, web.Application):
        app = default
    else:
        app = web.Application()

    options = SlimApplicationOptions()
    options.cookies_secret = cookies_secret
    options.session_cls = session_cls
    app._slim_options = options

    if enable_log:
        log.enable()

    if route:
        # 推后至启动时进行
        def on_available(app):
            route.bind(app)
        app.on_loop_available.append(on_available)

    return app
