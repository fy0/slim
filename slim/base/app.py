from aiohttp import web
from .session import SimpleSession
from . import log


class SlimApplicationOptions:
    def __init__(self):
        self.cookies_secret = b'use a secret'
        self.session_cls = SimpleSession


def app_init(cookies_secret: bytes, *, aiohttp_app_instance=None, enable_log=True, route=None, session_cls=SimpleSession)\
        -> web.Application:
    if isinstance(aiohttp_app_instance, dict):
        # noinspection PyArgumentList
        app = web.Application(**aiohttp_app_instance)
    elif isinstance(aiohttp_app_instance, web.Application):
        app = aiohttp_app_instance
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
        def on_available(the_app):
            route.bind(the_app)
        app.on_loop_available.append(on_available)

    return app
