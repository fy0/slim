from unittest import mock
from aiohttp.test_utils import make_mocked_request


async def make_mocked_view_instance(app, view_cls, method, url, params=None, post=None, *, headers=None):
    request = make_mocked_request(method, url, headers=headers or {}, protocol=mock.Mock(), app=app)
    request._post = post
    view = view_cls(app, request)
    await view._prepare()
    view._params_cache = params
    return view
