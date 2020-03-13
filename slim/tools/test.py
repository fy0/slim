import inspect
import json
import logging
from ipaddress import ip_address
from typing import Optional, Callable, Union
from unittest import mock
from aiohttp.test_utils import make_mocked_request as _make_mocked_request
from peewee import SqliteDatabase

from slim import Application, ALL_PERMISSION
from slim.base._view.abstract_sql_view import AbstractSQLView
from slim.base.types.beacon import BeaconInfo
from slim.base.view import BaseView
from slim.support.peewee import PeeweeView


def new_app(permission=ALL_PERMISSION, log_level=logging.WARN, **kwargs) -> Application:
    """
    Get application instance
    :param permission:
    :param log_level:
    :param kwargs:
    :return:
    """
    app = Application(cookies_secret=b'123456', permission=permission, log_level=log_level, **kwargs)
    return app


def _polyfill_post(request, post):
    if post:
        try:
            request._read_bytes = bytes(json.dumps(post), 'utf-8')
        except TypeError:
            # logger.warning(...)
            pass
    else:
        request._read_bytes = b''


def get_peewee_db():
    """
    Get peewee database instance
    :return:
    """
    db = SqliteDatabase(":memory:")
    return db


async def make_mocked_view_instance(app, view_cls, method, url, params=None, post=None, *, headers=None) -> Union[BaseView, AbstractSQLView, PeeweeView]:
    if not headers:
        headers = {}
    headers['Content-Type'] = 'application/json'
    request = _make_mocked_request(method, url, headers=headers, protocol=mock.Mock(), app=app)
    _polyfill_post(request, post)

    view = view_cls(app, request)
    view._params_cache = params
    view._post_data_cache = post

    await view._prepare()
    return view


async def invoke_interface(app: Application, func: [Callable], params=None, post=None, *, headers=None, method=None,
                           user=None, bulk=False, role=None, json_request=True) -> Optional[BaseView]:
    """
    :param app:
    :param func:
    :param params:
    :param post:
    :param headers:
    :param method: auto detect
    :param user:
    :param bulk:
    :param role:
    :param json_request:
    :return:
    """
    url = 'mock_url'

    assert inspect.ismethod(func), 'func must be method. e.g. UserView().get'
    view_cls = func.__self__.__class__
    func = func.__func__

    beacon_info_dict = app.route._handler_to_beacon_info.get(func)
    beacon_info: BeaconInfo = beacon_info_dict.get(view_cls) if beacon_info_dict else None

    if beacon_info:
        beacon_func = beacon_info.beacon_func
        info = app.route._beacons[beacon_func]
        url = info.route.fullpath
        _method = next(iter(info.route.method))

        if method:
            _method = method

        headers = headers or {}
        if bulk:
            headers['bulk'] = bulk
        if role:
            headers['role'] = role

        if json_request:
            headers['Content-Type'] = 'application/json'

        request = _make_mocked_request(_method, url, headers=headers, protocol=mock.Mock(), app=app)
        _polyfill_post(request, post)

        view_ref: Optional[BaseView] = None

        def hack_view(view: BaseView):
            nonlocal view_ref
            view_ref = view
            view._params_cache = params
            view._post_data_cache = post
            view._ip_cache = ip_address('127.0.0.1')
            view._current_user = user

        await app._request_solver(request, beacon_func, hack_view)
        assert view_ref, 'Invoke interface failed. Did you call `app._prepare()`?'
        return view_ref
