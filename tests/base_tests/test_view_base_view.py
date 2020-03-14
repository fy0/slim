from unittest import mock

import pytest

from slim.base._view.base_view import BaseView
from aiohttp.test_utils import make_mocked_request as _make_mocked_request
from slim import Application, ALL_PERMISSION
from slim.tools.test import _polyfill_post

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)


@app.route('topic')
class TopicView(BaseView):
    pass


app._prepare()


def make_req(method, data=None, raw_data: bytes = None):
    headers = {'Content-Type': 'application/json'}
    request = _make_mocked_request(method, '/x', headers=headers, protocol=mock.Mock(), app=app)
    if raw_data:
        request._read_bytes = raw_data
    else:
        _polyfill_post(request, data)
    return request


async def test_view_method():
    view = TopicView(app, make_req('POST'))
    assert view.method == 'POST'


async def test_view_postdata_json():
    view = TopicView(app, make_req('POST', data={'test': 111}))
    post = await view.post_data()
    assert post['test'] == 111


async def test_view_postdata_invalid_method():
    view = TopicView(app, make_req('GET', data={'test': 111}))
    assert (await view.post_data()) is None


async def test_view_postdata_invalid_json():
    view = TopicView(app, make_req('POST', raw_data=b'{'))
    assert (await view.post_data()) == {}
