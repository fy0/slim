
from aiohttp import web
from mapi.permission import Permission


class Resource:
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小
    permission_type = Permission
    surface = {
        'get': 'GET',
        'list': [
            {
                'method': 'GET',
                'url': '/list/{page}'
            },
            {
                'method': 'GET',
                'url': '/list/{page}/{size}'
            },
        ],
        'set': 'POST',
        'new': 'POST',
        'del': 'POST',
    }

    @staticmethod
    def _surface_list_tmpl(name):
        return [
            {
                'method': 'GET',
                'url': '/%s/{page}' % name
            },
            {
                'method': 'GET',
                'url': '/%s/{page}/{size}' % name
            },
        ]

    def __init__(self):
        self.ret_val = None
        self.permission = self.permission_type(self)

    def query_and_store_handle(self, key, value):
        """
        在查询和存入值时做额外的处理，并将结果返回
        例如存入密码时，要哈希化，后续查询时要将查询的值也哈希化
        :param key: 将要保存的键
        :param value: 将要保存的值
        :return: 处理后的值
        """
        return value

    async def prepare(self, request):
        pass

    def finish(self, code, data=None):
        self.ret_val = web.json_response({'code': code, 'data': data})

    def bind(self, app, name=None):
        """
        将 API 绑定到 web 服务上
        :param app: 
        :param name: 
        :return: 
        """
        name = name or self.__class__.__name__.lower()

        def wrap(name, func):
            async def wfunc(*args, **kwargs):
                request = args[0]
                self.permission.is_valid(name, request)
                await self.prepare(request)
                ret = await func(*args, **kwargs)
                return ret if ret is not None else self.ret_val

            return wfunc

        def add_route(key, item, request_handler):
            if type(item) == str:
                app.router.add_route(item, '/api/%s/%s' % (name, key), wrap(name, request_handler))
            elif type(item) == dict:
                methods = item['method']
                if type(methods) == str:
                    methods = [methods]
                elif type(methods) not in (list, set, tuple):
                    raise BaseException('Invalid type of route config description: %s', type(item))

                for i in methods:
                    if 'url' in item:
                        app.router.add_route(i, '/api/%s%s' % (name, item['url']), wrap(name, request_handler))
                    else:
                        app.router.add_route(i, '/api/%s/%s' % (name, key), wrap(name, request_handler))
            elif type(item) in (list, set, tuple):
                for i in item:
                    add_route(key, i, request_handler)
            else:
                raise BaseException('Invalid type of route config description: %s', type(item))

        for key, http_method in self.surface.items():
            request_handler = getattr(self, key, None)
            if request_handler: add_route(key, http_method, request_handler)

    # 举例：
    # async def get(self, request):
    #     self.finish(0, {})
