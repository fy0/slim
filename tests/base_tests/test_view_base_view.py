import json
import pytest

from slim.base._view.base_view import BaseView
from slim.base.web import FileField
from slim import Application, ALL_PERMISSION
from slim.exception import PermissionDenied, InvalidPostData
from slim.retcode import RETCODE
from slim.tools.test import invoke_interface, make_mocked_request

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)


@app.route.view('topic')
class TopicView(BaseView):
    @app.route.interface('POST')
    async def upload(self):
        post = await self.post_data()
        field = post.get('file')
        assert isinstance(field, FileField)
        assert field.file.read() == b'FILE_CONTENT'
        self.finish(RETCODE.SUCCESS)


app.prepare()


def make_req(method, data=None, raw_data: bytes = None):
    headers = {'Content-Type': 'application/json'}
    if data:
        raw_data = json.dumps(data).encode('utf-8')
    return make_mocked_request(method, '/any', headers=headers, body=raw_data)


async def test_view_method():
    view = TopicView(app, make_mocked_request('POST', '/any'))
    assert view.method == 'POST'


async def test_view_postdata_json():
    view = TopicView(app, make_req('POST', data={'test': 111}))
    post = await view.post_data()
    assert post['test'] == 111


async def test_view_postdata_get():
    view = TopicView(app, make_req('GET', data={'test': 111}))
    post = await view.post_data()
    assert post['test'] == 111


async def test_view_postdata_invalid_json():
    view = TopicView(app, make_req('POST', raw_data=b'{'))
    with pytest.raises(InvalidPostData) as e:
        await view.post_data()


async def test_view_post_file():
    post_raw = b'------WebKitFormBoundaryRanewtcan8ETWm3N\r\nContent-Disposition: form-data; name="file"; filename="hhhh.txt"\r\nContent-Type: text/plain\r\n\r\nFILE_CONTENT\r\n------WebKitFormBoundaryRanewtcan8ETWm3N--\r\n'
    await invoke_interface(app, TopicView().upload, content_type='multipart/form-data; boundary=----WebKitFormBoundaryRanewtcan8ETWm3N', body=post_raw)
