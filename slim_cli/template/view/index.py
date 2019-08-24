from aiohttp import web
from slim.base.view import BaseView
from slim.retcode import RETCODE
from app import app


@app.route('misc')
class TestBaseView(BaseView):
    @app.route.interface('GET')
    async def info(self):
        self.finish(RETCODE.SUCCESS, {
            'retcode': RETCODE.to_dict(),
            'retinfo': RETCODE.txt_cn,
        })

    @app.route.interface('POST')
    async def hello(self):
        data = await self.post_data()
        self.finish(RETCODE.SUCCESS, 'Hi, %s' % data.get('name', 'visitor'))


@app.route('/api/aiohttp_request')
async def hello(request):
    return web.Response(text='hello')
