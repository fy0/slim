import asyncio
import logging
import time
import traceback
from typing import TYPE_CHECKING

from .request import ASGIRequest
from .response import Response, JSONResponse
from ..types.asgi import Scope, Receive, Send
from ..types.route_meta_info import RouteStaticsInfo, RouteViewInfo
from slim.utils import async_call

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from slim import Application, CORSOptions
    from slim.base.view.base_view import BaseView


async def handle_request(app: 'Application', scope: Scope, receive: Receive, send: Send, *, raise_for_resp=False):
    """
    Handle http request
    :param app:
    :param scope:
    :param receive:
    :param send:
    :return:
    """
    from ..view.validate import view_validate_check

    if scope['type'] == 'lifespan':
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                try:
                    app.prepare()
                    for func in app.on_startup:
                        await async_call(func)

                    for i in app.route._views:
                        i: RouteViewInfo
                        await i.view_cls.on_init()

                    app.running = True

                    # start timer
                    for interval_seconds, runner in app._timers_before_running:
                        loop = asyncio.get_event_loop()
                        loop.call_later(interval_seconds, runner)

                    await send({'type': 'lifespan.startup.complete'})
                except Exception:
                    traceback.print_exc()
                    await send({'type': 'lifespan.startup.failed'})
                    return

            elif message['type'] == 'lifespan.shutdown':
                for func in app.on_shutdown:
                    await async_call(func)

                await send({'type': 'lifespan.shutdown.complete'})
                return

    if scope['type'] == 'http':
        t = time.perf_counter()
        handler_name = None
        view = None

        request = ASGIRequest(scope, receive, send)
        resp = None

        try:
            if request.method == 'OPTIONS':
                resp = Response(200)
            else:
                route_info, call_kwargs_raw = app.route.query_path(scope['method'], scope['path'])

                if route_info:
                    handler_name = route_info.get_handler_name()

                    if isinstance(route_info, RouteStaticsInfo):
                        resp = await route_info.responder.solve(request, call_kwargs_raw.get('file'))
                    else:
                        # filter call_kwargs
                        call_kwargs = call_kwargs_raw.copy()
                        if route_info.names_varkw is not None:
                            for j in route_info.names_exclude:
                                if j in call_kwargs:
                                    del call_kwargs[j]

                        for j in call_kwargs.keys() - route_info.names_include:
                            del call_kwargs[j]

                        # build a sqlview instance
                        view = await route_info.view_cls._build(app, request)
                        view._call_kwargs = call_kwargs
                        view._route_info = route_info
                        app._last_view = view

                        # if isinstance(view, AbstractSQLView):
                        #     view.current_interface = route_info.builtin_interface

                        # make the method bounded
                        handler = route_info.handler.__get__(view)

                        # note: sqlview.prepare() may case finished
                        if not view.is_finished:
                            # user's validator check
                            await view_validate_check(view, route_info.va_query, route_info.va_post, route_info.va_headers)

                            ret_resp = None
                            if not view.is_finished:
                                # call the request handler
                                if asyncio.iscoroutinefunction(handler):
                                    view_ret = await handler(**call_kwargs)
                                else:
                                    view_ret = handler(**call_kwargs)

                                if not view.response:
                                    if isinstance(view_ret, Response):
                                        view.response = view_ret
                                    else:
                                        view.response = JSONResponse(200, view_ret)

                        view: BaseView
                        await view._on_finish()
                        resp = view.response

            if not resp:
                resp = Response(404, b"Not Found")

        except Exception as e:
            traceback.print_exc()
            resp = Response(500, b"Internal Server Error")

        try:
            # Configure CORS settings.
            if app.cors_options:
                # TODO: host match
                for i in app.cors_options:
                    i: CORSOptions
                    if resp.headers:
                        resp.headers.update(i.pack_headers(request))
                    else:
                        resp.headers = i.pack_headers(request)

            app._last_resp = resp
            await resp(scope, receive, send)

            took = round((time.perf_counter() - t) * 1000, 2)
            # GET /api/get -> TopicView.get 200 30ms
            path = scope['path']
            if scope['query_string']:
                path += '?' + scope['query_string'].decode('ascii')

            if handler_name:
                logger.info("{} - {:15s} {:8s} {} -> {}, took {}ms".format(resp.status, scope['client'][0], scope['method'], path, handler_name, took))
            else:
                logger.info("{} - {:15s} {:8s} {}, took {}ms".format(resp.status, scope['client'][0], scope['method'], path, took))

            if view:  # for debug
                return view

        except Exception as e:
            if raise_for_resp:
                raise e
            else:
                traceback.print_exc()

    elif scope['type'] == 'websocket':
        request = ASGIRequest(scope, receive, send)
        route_info, call_kwargs_raw = app.route.query_ws_path(scope['path'])

        if route_info:
            # handler_name = route_info.get_handler_name()
            ws = route_info.ws_cls(app, request, call_kwargs_raw)
            await ws._prepare()
            await ws(scope, receive, send)
        else:
            # refuse connect
            await send({'type': 'websocket.close'})

    else:
        raise NotImplementedError(f"Unknown scope type {scope['type']}")
