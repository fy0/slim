from unittest import mock

import pytest
from aiohttp.web_request import FileField

from slim.base._view.base_view import BaseView
from aiohttp.test_utils import make_mocked_request as _make_mocked_request
from slim import Application, ALL_PERMISSION
from slim.retcode import RETCODE
from slim.tools.test import _polyfill_post, invoke_interface

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)


@app.route.view('topic')
class TopicView(BaseView):
    @app.route.interface('POST')
    async def upload(self):
        post = await self.post_data()
        field: FileField = post.get('file')
        assert isinstance(field, FileField)
        assert field.file.read() == b'FILE_CONTENT'
        self.finish(RETCODE.SUCCESS)


app.prepare()


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


async def test_view_post_file():
    post_raw = b'------WebKitFormBoundaryRanewtcan8ETWm3N\r\nContent-Disposition: form-data; name="file"; filename="hhhh.txt"\r\nContent-Type: text/plain\r\n\r\nFILE_CONTENT\r\n------WebKitFormBoundaryRanewtcan8ETWm3N--\r\n'
    await invoke_interface(app, TopicView().upload, content_type='multipart/form-data; boundary=----WebKitFormBoundaryRanewtcan8ETWm3N', post=post_raw, fill_post_cache=False)
