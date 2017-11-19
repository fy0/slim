import asyncio
import json
import logging
import time
from typing import Tuple, Union, Dict, Iterable, Type
from aiohttp import web

from .app import SlimApplicationOptions
from .helper import create_signed_value, decode_signed_value
from .permission import Permissions, Ability, A
from .sqlfuncs import AbstractSQLFunctions
from ..retcode import RETCODE
from ..utils import MetaClassForInit
from ..utils.others import valid_sql_operator
from ..exception import ResourceException, ValueHandleException

logger = logging.getLogger(__name__)


class BasicView(metaclass=MetaClassForInit):
    """
    应在 cls_init 时完成全部接口的扫描与wrap函数创建
    并在wrapper函数中进行实例化，传入 request 对象
    """
    _interface = {}
    # permission: Permissions  # 3.6

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
    def permission_init(cls):
        """ Override it """
        cls.permission.add(Ability(None, {'*': '*'}))

    @classmethod
    def cls_init(cls):
        cls._interface = {}
        cls.interface()
        if getattr(cls, 'permission', None):
            cls.permission = cls.permission.copy()
        else:
            cls.permission = Permissions()
        cls.permission_init()

    def __init__(self, request: web.web_request.Request):
        self.request = request
        self.ret_val = None
        self.response = None
        self.session = None
        self._cookie_set = None
        self._params_cache = None
        self._post_data_cache = None
        self._post_json_cache = None
        self._current_user = None

    @property
    def is_finished(self):
        return self.response

    async def _prepare(self):
        session_cls = self.slim_options.session_cls
        self.session = await session_cls.get_session(self)

    async def prepare(self):
        pass

    @property
    def current_user(self):
        if not self._current_user:
            self._current_user = self.get_current_user()
        return self._current_user

    def get_current_user(self):
        """Override to determine the current user from, e.g., a cookie.
        """
        return None

    def finish(self, code, data=NotImplemented):
        if data is NotImplemented:
            data = RETCODE.txt_cn.get(code)
        self.ret_val = {'code': code, 'data': data}  # for access in inhreads method
        self.response = web.json_response(self.ret_val)
        logger.debug('finish: %s' % self.ret_val)
        for i in self._cookie_set or ():
            if i[0] == 'set':
                self.response.set_cookie(i[1], i[2], **i[3])
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

    async def _post_json(self) -> dict:
        # post body: raw(text) json
        if self._post_json_cache is None:
            self._post_json_cache = dict(await self.request.json())
        return self._post_json_cache

    async def post_data(self) -> dict:
        # post body: form data
        if self._post_data_cache is None:
            self._post_data_cache = dict(await self.request.post())
            logger.debug('raw post data: %s', self._post_data_cache)
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

    @property
    def slim_options(self) -> SlimApplicationOptions:
        return self.request.app._slim_options

    def set_secure_cookie(self, name, value: bytes, *, max_age=30):
        #  一般来说是 UTC
        # https://stackoverflow.com/questions/16554887/does-pythons-time-time-return-a-timestamp-in-utc
        timestamp = int(time.time())
        # version, utctime, name, value
        # assert isinatance(value, (str, list, tuple, bytes, int))
        to_sign = [1, timestamp, name, value]
        secret = self.slim_options.cookies_secret
        self.set_cookie(name, create_signed_value(secret, to_sign), max_age=max_age)

    def get_secure_cookie(self, name, default=None, max_age_days=31):
        secret = self.slim_options.cookies_secret
        value = self.get_cookie(name)
        if value:
            data = decode_signed_value(secret, value)
            # TODO: max_age_days 过期计算
            if data and data[2] == name:
                return data[3]
        return default


class QueryArguments(list):
    """ 与 list 实际没有太大不同，独立为类型的目的是使其能与list区分开来 """
    def __contains__(self, item):
        for i in self:
            if i[0] == item:
                return True

    def map(self, key, func):
        for i in self:
            if i[0] == key:
                i[:] = func(i)


class ParamsQueryInfo(dict):
    """ 目的同 QueryArguments，即与其他 dict 能够区分 """
    @property
    def args(self) -> QueryArguments:
        return self['args']

    @property
    def orders(self):
        return self['orders']

    @property
    def select(self):
        return self['select']


class ViewOptions:
    def __init__(self, *, list_page_size=20, list_accept_size_from_client=False, permission: Permissions=None):
        self.list_page_size = list_page_size
        self.list_accept_size_from_client = list_accept_size_from_client
        self.permission = permission

    def assign(self, obj: Type['AbstractSQLView']):
        obj.LIST_PAGE_SIZE = self.list_page_size
        obj.LIST_ACCEPT_SIZE_FROM_CLIENT = self.list_accept_size_from_client
        if self.permission:
            obj.permission = self.permission


# noinspection PyMethodMayBeStatic
class AbstractSQLView(BasicView):
    options_cls = ViewOptions
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小
    LIST_ACCEPT_SIZE_FROM_CLIENT = False

    fields = {}
    table_name = ''

    @classmethod
    def _check_view_options(cls):
        options = getattr(cls, 'options', None)
        if options and isinstance(options, ViewOptions):
            options.assign(cls)

    @classmethod
    def cls_init(cls, check_options=True):
        if check_options:
            cls._check_view_options()
        super().cls_init()

        async def func():
            return await cls._fetch_fields(cls)
        asyncio.get_event_loop().run_until_complete(func())

    def __init__(self, request):
        super().__init__(request)
        self._sql = AbstractSQLFunctions(self)

    async def _prepare(self):
        await super()._prepare()
        value = self.request.headers.get('Role')
        role = int(value) if value and value.isdigit() else value
        self.ability = self.permission.request_role(self.current_user, role)
        if not self.ability:
            self.finish(RETCODE.INVALID_ROLE)

    def _parse_order(self, text):
        """
        :param text: order=id.desc, xxx.asc
        :return: 
        """
        orders = []
        for i in text.split(','):
            items = i.split('.', 2)

            if len(items) == 1: column, order = items[0], 'default'
            elif len(items) == 2: column, order = items
            else: raise ResourceException("Invalid order format")

            order = order.lower()
            if column not in self.fields:
                raise ResourceException('Column not found: %s' % column)
            if order not in ('asc', 'desc', 'default'):
                raise ResourceException('Invalid column order: %s' % order)

            orders.append([column, order])
        return orders

    def _parse_select(self, text: str):
        """
        get columns from select text
        :param text: col1, col2
        :return: None or [col1, col2]
        """
        info = set(text.split(','))
        if '*' in info:
            return None
        else:
            selected_columns = []
            for column in info:
                if column:
                    if column not in self.fields:
                        raise ResourceException('Column not found: %s' % column)
                    selected_columns.append(column)
            assert selected_columns, "No column(s) selected"
            return selected_columns

    def _parse_params(self, params) -> Union[ParamsQueryInfo, None]:
        """ parse params to query information """
        args = QueryArguments()
        ret = ParamsQueryInfo(
            select=None,
            args=args,
            orders=[],
            format='dict'
        )

        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]
            if field_name == 'order':
                ret['orders'] = self._parse_order(value)
                continue
            elif field_name == 'select':
                ret['select'] = self._parse_select(value)
                continue
            elif field_name == '_data_format':
                ret['format'] = value
                continue
            op = '='

            if field_name not in self.fields:
                self.finish(RETCODE.INVALID_HTTP_PARAMS, 'Column not found: %s' % field_name)
                return

            if len(info) > 1:
                op = info[1]
                if op not in valid_sql_operator:
                    self.finish(RETCODE.INVALID_HTTP_PARAMS, 'Invalid operator: %s' % op)
                    return
                op = valid_sql_operator[op]

            # is 和 is not 可以确保完成了初步值转换
            if op in ('is', 'isnot'):
                if value.lower() != 'null':
                    self.finish(RETCODE.INVALID_HTTP_PARAMS, 'Invalid value: %s (must be null)' % value)
                    return
                if op == 'isnot':
                    op = 'is not'
                value = None

            if op == 'in':
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError:
                    self.finish(RETCODE.INVALID_HTTP_PARAMS, 'Invalid value: %s (must be json)' % value)
                    return

            args.append([field_name, op, value])

        # 查询权限检查
        from_columns = []
        for field_name, op, value in args:
            from_columns.append((self.table_name, field_name))
        if from_columns and all(self.ability.cannot(self.current_user, A.QUERY, *from_columns)):
            logger.debug('params: %s' % ret)
            return self.finish(RETCODE.PERMISSION_DENIED)

        # 读取权限检查，限定被查询的列
        if ret['select'] is None:
            ret['select'] = self.fields.keys()
        ret['select'] = self.ability.filter_columns(self.table_name, ret['select'], A.READ)

        logger.debug('params: %s' % ret)
        return ret

    def _filter_record_by_ability(self, record) -> Union[Dict, None]:
        available_columns = self.ability.filter_record(self.current_user, A.READ, record)
        if not available_columns: return
        return record.to_dict(available_columns)

    def _call_handle_fix(self, ret):
        """ check result of handle_query/read/insert/update """
        if ret is None:
            return

        if isinstance(ret, Iterable):
            return self.finish(*ret)

        raise ValueHandleException('Invalid result type of handle function.')

    async def get(self):
        info = self._parse_params(self.params())
        if self.is_finished: return
        self._call_handle_fix(self.handle_query(info))
        if self.is_finished: return
        logger.debug('query info: %s', info)
        code, data = await self._sql.select_one(info)

        if code == RETCODE.SUCCESS:
            data = self._filter_record_by_ability(data)
            if not data: return self.finish(RETCODE.NOT_FOUND)
            self._call_handle_fix(self.handle_read(data))
            if self.is_finished: return
        self.finish(code, data)

    def _get_list_page_and_size(self) -> Tuple[Union[int, None], Union[int, None]]:
        page = self.request.match_info.get('page', '1')

        if not page.isdigit():
            self.finish(RETCODE.INVALID_HTTP_PARAMS)
            return None, None
        page = int(page)

        size = self.request.match_info.get('size', None)
        if self.LIST_ACCEPT_SIZE_FROM_CLIENT:
            if size:
                if size == '-1':  # size is infinite
                    size = -1
                elif size.isdigit():
                    size = int(size or self.LIST_PAGE_SIZE)
                else:
                    self.finish(RETCODE.INVALID_HTTP_PARAMS)
                    return None, None
            else:
                size = self.LIST_PAGE_SIZE
        else:
            size = self.LIST_PAGE_SIZE

        return page, size

    async def list(self):
        page, size = self._get_list_page_and_size()
        if self.is_finished: return
        info = self._parse_params(self.params())
        if self.is_finished: return
        self._call_handle_fix(self.handle_query(info))
        if self.is_finished: return

        code, data = await self._sql.select_paginated_list(info, size, page)

        if code == RETCODE.SUCCESS:
            lst = []
            get_values = lambda x: list(x.values())
            for i in data['items']:
                item = self._filter_record_by_ability(i)
                if not data: return self.finish(RETCODE.NOT_FOUND)

                if info['format'] == 'array':
                    item = get_values(item)
                self._call_handle_fix(self.handle_read(data))
                if self.is_finished: return
                lst.append(item)
            data['items'] = lst
            self.finish(RETCODE.SUCCESS, data)
        else:
            self.finish(code, data)

    def _data_convert(self, data: Dict[str, object], action=A.WRITE):
        # 写入/插入权限检查
        columns = []
        for k, v in data.items():
            columns.append((self.table_name, k))

        if len(columns) == 0:
            return self.finish(RETCODE.INVALID_HTTP_POSTDATA)

        if all(self.ability.cannot(self.current_user, action, *columns)):
            return self.finish(RETCODE.PERMISSION_DENIED)

        return data

    async def set(self):
        info = self._parse_params(self.params())
        if self.is_finished: return
        self._call_handle_fix(self.handle_query(info))
        if self.is_finished: return

        post_data = self._data_convert(await self.post_data())
        if self.is_finished: return
        self._call_handle_fix(self.handle_update(post_data))
        if self.is_finished: return

        logger.debug('data: %s' % post_data)
        code, data = await self._sql.update(info, post_data)
        self.finish(code, data)

    async def new(self):
        post_data = self._data_convert(await self.post_data(), action=A.CREATE)
        logger.debug('data: %s' % post_data)
        if self.is_finished: return
        self._call_handle_fix(self.handle_insert(post_data))
        if self.is_finished: return

        code, data = await self._sql.insert(post_data)
        if code == RETCODE.SUCCESS:
            data = self._filter_record_by_ability(data)
            if not data: return self.finish(RETCODE.NOT_FOUND)

            self._call_handle_fix(self.handle_read(data))
            if self.is_finished: return
        self.finish(code, data)

    @staticmethod
    async def _fetch_fields(cls_or_self):
        # raise NotImplementedError()
        pass

    def handle_query(self, info: ParamsQueryInfo) -> Union[None, tuple]:
        pass

    def handle_read(self, values: Dict) -> Union[None, tuple]:
        pass

    def handle_insert(self, values: Dict) -> Union[None, tuple]:
        pass

    def handle_update(self, values: Dict) -> Union[None, tuple]:
        pass
