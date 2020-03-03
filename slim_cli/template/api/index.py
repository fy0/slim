from slim.base.view import BaseView
from slim.retcode import RETCODE

from app import app


@app.route.view('misc', 'Misc API')
class MiscView(BaseView):
    @app.route.interface('GET')
    async def info(self):
        """
        提供给前端使用的后端配置信息
        """
        self.finish(RETCODE.SUCCESS, {
            'retcode': RETCODE.to_dict(),
            'retinfo': RETCODE.txt_cn,
        })

    @app.route.interface('POST')
    async def hello(self):
        data = await self.post_data()
        self.finish(RETCODE.SUCCESS, 'Hi, %s' % data.get('name', 'visitor'))
