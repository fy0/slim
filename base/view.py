import json
import asyncio
import logging
from aiohttp import web
from aiohttp_session import get_session
from ..retcode import RETCODE
from ..utils import time_readable, ResourceException, _valid_sql_operator, _MetaClassForInit, pagination_calc

logger = logging.getLogger(__name__)


class BasicMView(metaclass=_MetaClassForInit):
    """
    应在 cls_init 时完成全部接口的扫描与wrap函数创建
    并在wrapper函数中进行实例化，传入 request 对象
    """
    _interface = {}

    @classmethod
    def use(cls, name, method_or_lst, url=None):
        """ interface helper function"""
        if type(method_or_lst) == list:
            val = method_or_lst
        else:
            val = {'method': method_or_lst, 'url': url} if url else method_or_lst
        cls._interface[name] = val

    @classmethod
    def use_lst(cls, name):
        cls.use(name, [
            {'method': 'GET', 'url': '/%s/{page}' % name},
            {'method': 'GET', 'url': '/%s/{page}/{size}' % name},
        ])

    @classmethod
    def discard(cls, name):
        """ interface helper function"""
        cls._interface.pop(name, None)

    @classmethod
    def interface(cls):
        cls.use('get', 'GET')
        cls.use_lst('list')
        cls.use('set', 'POST')
        cls.use('new', 'POST')
        cls.use('delete', 'POST')

    @classmethod
    def cls_init(cls):
        cls._interface = {}
        cls.interface()

    def __init__(self, request):
        self.request = request
        self.ret_val = None
        self.response = None
        self.session = None
        self._cookie_set = None
        self._params_cache = None
        self._post_data_cache = None

    @property
    def is_finished(self):
        return self.response

    async def _prepare(self):
        self.session = await get_session(self.request)

    async def prepare(self):
        pass

    def finish(self, code, data=None):
        self.ret_val = {'code': code, 'data': data}  # for access in inhreads method
        self.response = web.json_response(self.ret_val)
        logger.debug('request finish: %s' % self.ret_val)
        for i in self._cookie_set or ():
            if i[0] == 'set':
                self.response.set_cookie(i[1], i[2], **i[3]) # secure not work
            else:
                self.response.del_cookie(i[1])

    def del_cookie(self, key):
        if self._cookie_set is None:
            self._cookie_set = []
        self._cookie_set.append(('del', key))

    def params(self) -> dict:
        if self._params_cache is None:
            self._params_cache = dict(self.request.query)
        return self._params_cache

    async def post_data(self) -> dict:
        if self._post_data_cache is None:
            self._post_data_cache = dict(await self.request.post())
        return self._post_data_cache

    def set_cookie(self, key, value, *, path='/', expires=None, domain=None, max_age=None, secure=None,
                   httponly=None, version=None):
        if self._cookie_set is None:
            self._cookie_set = []
        kwargs = {'path': path, 'expires': expires, 'domain': domain, 'max_age': max_age, 'secure': secure,
                  'httponly': httponly, 'version': version}
        self._cookie_set.append(('set', key, value, kwargs))

    def get_cookie(self, name, default=None):
        if self.request.cookies is not None and name in self.request.cookies:
            return self.request.cookies.get(name)
        return default

    async def set_secure_cookie(self, name, value, *, max_age=30, version=None):
        pass

    def get_secure_cookie(self, name, value=None, max_age=31):
        pass


class BaseSQLFunctions:
    def __init__(self, view: BasicMView):
        self.view = view
        self.request = view.request

    async def select_one(self, select_info):
        raise NotImplementedError()
        # code, item

    async def select_count(self, select_info):
        raise NotImplementedError()
        # code, count: int

    async def select_list(self, select_info, size, offset, *, page=None):
        raise NotImplementedError()
        # code, items: iterable

    async def update(self, select_info, data):
        raise NotImplementedError()
        # code, item

    async def insert(self, data):
        raise NotImplementedError()
        # code, item

    def done(self, code, data=None):
        return code, data


class MView(BasicMView):
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小
    LIST_ACCEPT_SIZE_FROM_CLIENT = False

    fields = {}
    table_name = ''
    sql_cls = BaseSQLFunctions

    @staticmethod
    async def _fetch_fields(cls_or_self):
        #raise NotImplementedError()
        pass

    def _get_list_page_and_size(self):
        page = self.request.match_info.get('page', '1')
        if not page.isdigit():
            self.finish(RETCODE.INVALID_PARAMS)
            return None, None
        page = int(page)

        size = self.request.match_info.get('size', None)
        if self.LIST_ACCEPT_SIZE_FROM_CLIENT:
            if size and not size.isdigit():
                self.finish(RETCODE.INVALID_PARAMS)
                return None, None
            size = int(size or self.LIST_PAGE_SIZE)
        else:
            size = self.LIST_PAGE_SIZE

        return page, size

    @classmethod
    def cls_init(cls):
        super().cls_init()
        async def func():
            return await cls._fetch_fields(cls)
        asyncio.get_event_loop().run_until_complete(func())

    def __init__(self, request):
        super().__init__(request)
        self._sql = self.sql_cls(self)

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
        ret = {
            'args': args,
            'orders': orders,
        }

        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]
            if field_name == 'order':
                orders = self._query_order(value)
                continue
            elif field_name == 'with_role':
                if not value.isdigit():
                    if len(info) < 1:
                        return self.finish(RETCODE.INVALID_PARAMS, 'Invalid role id: %s' % value)
                ret['with_role'] = int(value)
                continue
            op = '='

            if field_name not in self.fields:
                return self.finish(RETCODE.INVALID_PARAMS, 'Column not found: %s' % field_name)

            if len(info) > 1:
                op = info[1]
                if op not in _valid_sql_operator:
                    return self.finish(RETCODE.INVALID_PARAMS, 'Invalid operator: %s' % op)
                op = _valid_sql_operator[op]

            if op in ('is', 'isnot'):
                if value.lower() != 'null':
                    return self.finish(RETCODE.INVALID_PARAMS, 'Invalid value: %s (must be null)' % value)
                if op == 'isnot':
                    op = 'is not'
                value = None

            if op == 'in':
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError:
                    return self.finish(RETCODE.INVALID_PARAMS, 'Invalid value: %s' % value)

            args.append([field_name, op, value])

        logger.debug('params: %s' % ret)
        return ret

    async def get(self):
        info = self._query_convert(self.params())
        if self.is_finished: return
        #fails, columns_for_read = self.permission.check_select(self, request, args, orders, ext)
        #if fails: return self.fields(RETCODE.PERMISSION_DENIED, json.dumps(fails))
        code, data = await self._sql.select_one(info)
        self.finish(code, data)

    async def set(self):
        info = self._query_convert(self.params())
        if self.is_finished: return
        #fails, columns_for_read = self.permission.check_select(self, request, args, orders, ext)
        #if fails: return self.finish(RETCODE.PERMISSION_DENIED, fails)
        post_data = await self.post_data()
        logger.debug('data: %s' % post_data)
        code, data = await self._sql.update(info, post_data)
        self.finish(code, data)

    async def new(self):
        post_data = await self.post_data()
        logger.debug('data: %s' % post_data)
        code, data = await self._sql.insert(post_data)
        self.finish(code, data)

    async def list(self):
        page, size = self._get_list_page_and_size()
        if self.is_finished: return

        info = self._query_convert(self.params())
        if self.is_finished: return
        #fails, columns_for_read = self.permission.check_select(self, request, args, orders, ext)
        #if fails: return self.fields(RETCODE.PERMISSION_DENIED, json.dumps(fails))

        code, data = await self._sql.select_count(info)
        if code == RETCODE.SUCCESS:
            count = data
        else:
            return self.finish(code, data)

        pg = pagination_calc(count, size, page)
        offset = size * (page - 1)

        code, data = await self._sql.select_list(info, size, offset, page=page)
        if code == RETCODE.SUCCESS:
            pg["items"] = list(data)
            self.finish(RETCODE.SUCCESS, pg)
        else:
            self.finish(code, data)
