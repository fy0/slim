from aiohttp import web
from ..retcode import RETCODE
from ..utils import time_readable, ResourceException, _valid_sql_operator
from .permission import Permission, FakePermission


class Resource:
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小
    LIST_ALLOW_CLIENT_DEFINE_SIZE = True

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
    permission = FakePermission

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

    def _get_list_page_and_size(self, request):
        page = request.match_info.get('page', '1')
        if not page.isdigit():
            return self.finish(RETCODE.INVALID_PARAMS)
        page = int(page)

        size = request.match_info.get('size', None)
        if self.LIST_ALLOW_CLIENT_DEFINE_SIZE:
            if size and not size.isdigit():
                return self.finish(RETCODE.INVALID_PARAMS)
            size = int(size or self.LIST_PAGE_SIZE)
        else:
            size = self.LIST_PAGE_SIZE

        return page, size

    def __init__(self):
        self.ret_val = None

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
                await self.prepare(request)

                ascii_encodable_path = request.path.encode('ascii', 'backslashreplace').decode('ascii')
                print("[{}] {} {}".format(time_readable(), request._method, ascii_encodable_path))

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


class QueryResource(Resource):
    def __init__(self):
        super().__init__()
        self.table_name = None
        self.fields = {}

    def _query_order(self, text):
        """
        :param text: order=id.desc, xxx.asc
        :return: 
        """
        orders = []
        for i in text.split(','):
            items = i.split('.', 2)

            if len(items) == 1: continue
            elif len(items) == 2: column, order = items
            else: raise ResourceException("Invalid order format")

            order = order.lower()
            if column not in self.fields:
                raise ResourceException('Column not found: %s' % column)
            if order not in ('asc', 'desc'):
                raise ResourceException('Invalid column order: %s' % order)

            orders.append([column, order])
        return orders

    def _query_convert(self, params):
        args = []
        orders = []
        ext = {}

        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            if len(info) < 1:
                raise ResourceException('Invalid request parameter')

            field_name = info[0]
            if field_name == 'order':
                orders = self._query_order(value)
                continue
            elif field_name == 'with_role':
                if not value.isdigit():
                    raise ResourceException('Invalid role id: %s' % value)
                ext['with_role'] = int(value)
                continue
            op = '='

            if field_name not in self.fields:
                raise ResourceException('Column not found: %s' % field_name)

            if len(info) > 1:
                op = info[1]
                if op not in _valid_sql_operator:
                    raise ResourceException('Invalid operator: %s' % op)
                op = _valid_sql_operator[op]

            args.append([field_name, op, value])

        return args, orders, ext
