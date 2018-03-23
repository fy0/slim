import asyncio
import logging
import time
from abc import abstractmethod
from types import FunctionType
from typing import Tuple, Union, Dict, Iterable, Type, List, Set
from aiohttp import web

from .query import ParamsQueryInfo
from .app import Application
from .helper import create_signed_value, decode_signed_value
from .permission import Permissions, Ability, BaseUser, A
from .sqlfuncs import AbstractSQLFunctions, UpdateInfo
from ..retcode import RETCODE
from ..utils import MetaClassForInit, dict_filter, sync_call, async_call
from ..exception import ValueHandleException

logger = logging.getLogger(__name__)


class BaseView(metaclass=MetaClassForInit):
    """
    应在 cls_init 时完成全部接口的扫描与wrap函数创建
    并在wrapper函数中进行实例化，传入 request 对象
    """
    _interface = {}
    _no_route = False
    # permission: Permissions  # 3.6

    @classmethod
    def use(cls, name, method: [str, Set, List], url=None):
        """ interface helper function"""
        if not isinstance(method, (str, list, set, tuple)):
            raise BaseException('Invalid type of method: %s' % type(method).__name__)

        if isinstance(method, str):
            method = {method}

        # TODO: check methods available
        cls._interface[name] = [{'method': method, 'url': url}]

    @classmethod
    def use_lst(cls, name):
        cls._interface[name] = [
            {'method': {'GET'}, 'url': '%s/{page}' % name},
            {'method': {'GET'}, 'url': '%s/{page}/{size}' % name},
        ]

    @classmethod
    def discard(cls, name):
        """ interface helper function"""
        cls._interface.pop(name, None)

    @classmethod
    def interface(cls):
        pass

    @classmethod
    def permission_init(cls):
        """ Override it """
        cls.permission.add(Ability(None, {'*': '*'}))

    @classmethod
    def cls_init(cls):
        cls._interface = {}
        cls.interface()
        for k, v in vars(cls).items():
            if isinstance(v, FunctionType):
                if getattr(v, '_interface', None):
                    cls.use(k, *v._interface)
        if getattr(cls, 'permission', None):
            cls.permission = cls.permission.copy()
        else:
            cls.permission = Permissions()
        cls.permission_init()

    def __init__(self, app: Application, aiohttp_request: web.web_request.Request):
        self.app = app
        self._request = aiohttp_request

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
        return self.response is not None

    async def _prepare(self):
        session_cls = self.app.options.session_cls
        self.session = await session_cls.get_session(self)

    async def prepare(self):
        pass

    async def _on_finish(self):
        if self.session:
            await self.session.save()

    async def on_finish(self):
        pass

    @property
    def current_user(self) -> BaseUser:
        if not self._current_user:
            if getattr(self, 'get_current_user', None):
                self._current_user = self.get_current_user()
            else:
                self._current_user = None
        return self._current_user

    @property
    def current_user_roles(self):
        u = self.current_user
        if u is None:
            return {None}
        return u.roles

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

    @property
    def params(self) -> dict:
        if self._params_cache is None:
            self._params_cache = dict(self._request.query)
        return self._params_cache

    async def _post_json(self) -> dict:
        # post body: raw(text) json
        if self._post_json_cache is None:
            self._post_json_cache = dict(await self._request.json())
        return self._post_json_cache

    async def post_data(self) -> dict:
        # post body: form data
        if self._post_data_cache is None:
            self._post_data_cache = dict(await self._request.post())
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
        if self._request.cookies is not None and name in self._request.cookies:
            return self._request.cookies.get(name)
        return default

    def set_secure_cookie(self, name, value: bytes, *, httponly=True, max_age=30):
        #  一般来说是 UTC
        # https://stackoverflow.com/questions/16554887/does-pythons-time-time-return-a-timestamp-in-utc
        timestamp = int(time.time())
        # version, utctime, name, value
        # assert isinatance(value, (str, list, tuple, bytes, int))
        to_sign = [1, timestamp, name, value]
        secret = self.app.options.cookies_secret
        self.set_cookie(name, create_signed_value(secret, to_sign), max_age=max_age, httponly=httponly)

    def get_secure_cookie(self, name, default=None, max_age_days=31):
        secret = self.app.options.cookies_secret
        value = self.get_cookie(name)
        if value:
            data = decode_signed_value(secret, value)
            # TODO: max_age_days 过期计算
            if data and data[2] == name:
                return data[3]
        return default

    @property
    def headers(self):
        return self._request.headers

    @property
    def route_info(self):
        """
        info matched by router
        :return:
        """
        return self._request.match_info

    @classmethod
    def _ready(cls):
        """ private version of cls.ready() """
        cls.ready()

    @classmethod
    def ready(cls):
        """
        All modules loaded, and ready to serve.
        Emitted after register routes and before loop start
        :return:
        """
        pass


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
class AbstractSQLView(BaseView):
    _sql_cls = AbstractSQLFunctions
    is_base_class = True  # skip cls_init check
    foreign_keys_table_alias = {}  # to hide real table name

    options_cls = ViewOptions
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小
    LIST_ACCEPT_SIZE_FROM_CLIENT = False

    fields = {} # :[str, object], key is column, value can be everything
    table_name = ''
    primary_key = None
    foreign_keys = {} # :[str, [str]], key is column, value is table names (because of soft foreign keys, multi foreigns on one column is valid)

    @classmethod
    def _is_skip_check(cls):
        skip_check = False
        if 'is_base_class' in cls.__dict__:
            skip_check = getattr(cls, 'is_base_class')
        return skip_check

    @classmethod
    def interface(cls):
        super().interface()
        cls.use('get', 'GET')
        cls.use_lst('list')
        cls.use('set', 'POST')
        cls.use('new', 'POST')
        cls.use('delete', 'POST')

    @classmethod
    def add_soft_foreign_key(cls, column, table, alias=None):
        """
        the column stores foreign table's primary key but isn't a foreign key (to avoid constraint)
        warning: if the table not exists, will crash when query with loadfk
        :param column: table's column
        :param table: foreign table name
        :param alias: table name's alias, avoid exposed table name
        :return: True, None
        """
        if column in cls.fields:
            if alias:
                if alias in cls.foreign_keys_table_alias:
                    logger.warning("This alias of table is already exists, overwriting: %s.%s to %s" %
                                   (cls.__name__, column, table))
                cls.foreign_keys_table_alias[alias] = table
            if column not in cls.foreign_keys:
                cls.foreign_keys[column] = [table]
            else:
                if not alias:
                    logger.warning("This soft foreign key is useless, an alias required: %s.%s to %s" %
                                   (cls.__name__, column, table))
                cls.foreign_keys[column].append(table)
            return True

    @classmethod
    def _check_view_options(cls):
        options = getattr(cls, 'options', None)
        if options and isinstance(options, ViewOptions):
            options.assign(cls)

    @classmethod
    def cls_init(cls, check_options=True):
        if check_options:
            cls._check_view_options()

        # because of BaseView.cls_init is a bound method (@classmethod)
        # so we can only route BaseView._interface, not cls._interface defined by user
        BaseView.cls_init.__func__(cls)
        # super().cls_init()  # fixed in 3.6

        async def func():
            await cls._fetch_fields(cls)
            if not cls._is_skip_check():
                assert cls.table_name
                assert cls.fields
                # assert cls.primary_key
                # assert cls.foreign_keys

        asyncio.get_event_loop().run_until_complete(func())

    def _load_role(self, role):
        self.ability = self.permission.request_role(self.current_user, role)
        return self.ability

    @property
    def current_role(self) -> [int, str]:
        role_val = self.headers.get('Role')
        return int(role_val) if role_val and role_val.isdigit() else role_val

    async def _prepare(self):
        await super()._prepare()
        # _sql 里使用了 self.err 存放数据
        # 那么可以推测在并发中，cls._sql.err 会被多方共用导致出错
        self._sql = self._sql_cls(self.__class__)
        if not self._load_role(self.current_role):
            logger.debug("load role %r failed, please make sure the user is permitted and the View object inherited a UserMixin." % self.current_role)
            self.finish(RETCODE.INVALID_ROLE)

    async def load_fk(self, info, items) -> List:
        """
        :param info:
        :param items: the data got from database and filtered from permission
        :return:
        """
        # if not items, items is probably [], so return itself.
        if not items: return items
        # first: get tables' instances
        #table_map = {}
        #for column in info['loadfk'].keys():
        #    tbl_name = self.foreign_keys[column][0]
        #    table_map[column] = self.app.tables[tbl_name]

        # second: get query parameters
        async def check(data, items):
            for column, fkdatas in data.items():
                for fkdata in fkdatas:
                    pks = []
                    all_ni = True
                    for i in items:
                        val = i.get(column, NotImplemented)
                        if val != NotImplemented:
                            all_ni = False
                        pks.append(val)

                    if all_ni:
                        logger.debug("load foreign key failed, do you have read permission to the column %r?" % column)
                        continue

                    # third: query foreign keys
                    vcls = self.app.tables[fkdata['table']]
                    ability = vcls.permission.request_role(self.current_user, fkdata['role'])
                    info2 = ParamsQueryInfo(vcls)

                    info2.add_condition(info.PRIMARY_KEY, 'in', pks)
                    info2.set_select(None)
                    info2.check_permission(ability)

                    # vcls: AbstractSQLView
                    _sql = vcls._sql_cls(vcls)
                    code, data = await _sql.select_paginated_list(info2, -1, 1)
                    pk_values = _sql.convert_list_result(info2['format'], data)

                    # TODO: 别忘了！这里还少一个对结果的权限检查！

                    fk_dict = {}
                    for i in pk_values:
                        # 主键: 数据
                        fk_dict[i[vcls.primary_key]] = i

                    column_to_set = fkdata.get('as', column) or column
                    for _, item in enumerate(items):
                        k = item.get(column, NotImplemented)
                        if k in fk_dict:
                            item[column_to_set] = fk_dict[k]

                    if 'loadfk' in fkdata:
                        await check(fkdata['loadfk'], pk_values)

        await check(info['loadfk'], items)
        return items

    def _filter_record_by_ability(self, record) -> Union[Dict, None]:
        available_columns = self.ability.can_with_record(self.current_user, A.READ, record)
        if not available_columns: return
        return record.to_dict(available_columns)

    def _check_handle_result(self, ret):
        """ check result of handle_query/read/insert/update """
        if ret is None:
            return

        if isinstance(ret, Iterable):
            return self.finish(*ret)

        raise ValueHandleException('Invalid result type of handle function.')

    async def get(self):
        info = ParamsQueryInfo.new(self, self.params, self.ability)
        self._check_handle_result(await async_call(self.handle_query, info))
        if self.is_finished: return
        code, data = await self._sql.select_one(info)

        if code == RETCODE.SUCCESS:
            data = self._filter_record_by_ability(data)
            if not data: return self.finish(RETCODE.NOT_FOUND)
            self._check_handle_result(await async_call(self.after_read, data))
            if self.is_finished: return
            data = (await self.load_fk(info, [data]))[0]

        self.finish(code, data)

    def _get_list_page_and_size(self) -> Tuple[Union[int, None], Union[int, None]]:
        page = self.route_info.get('page', '1')

        if not page.isdigit():
            self.finish(RETCODE.INVALID_PARAMS)
            return None, None
        page = int(page)

        size = self.route_info.get('size', None)
        if self.LIST_ACCEPT_SIZE_FROM_CLIENT:
            if size:
                if size == '-1':  # size is infinite
                    size = -1
                elif size.isdigit():
                    size = int(size or self.LIST_PAGE_SIZE)
                else:
                    self.finish(RETCODE.INVALID_PARAMS)
                    return None, None
            else:
                size = self.LIST_PAGE_SIZE
        else:
            size = self.LIST_PAGE_SIZE

        return page, size

    async def _convert_list_result(self, info, data):
        lst = []
        get_values = lambda x: list(x.values())
        for i in data['items']:
            item = self._filter_record_by_ability(i)
            if not data: return self.finish(RETCODE.NOT_FOUND)

            if info['format'] == 'array':
                item = get_values(item)

            self._check_handle_result(await async_call(self.after_read, item))
            if self.is_finished: return
            lst.append(item)
        return lst

    async def list(self):
        page, size = self._get_list_page_and_size()
        if self.is_finished: return
        info = ParamsQueryInfo.new(self, self.params, self.ability)
        self._check_handle_result(await async_call(self.handle_query, info))
        if self.is_finished: return

        code, data = await self._sql.select_paginated_list(info, size, page)

        if code == RETCODE.SUCCESS:
            lst = await self._convert_list_result(info, data)
            data['items'] = await self.load_fk(info, lst)
            self.finish(RETCODE.SUCCESS, data)
        else:
            self.finish(code, data)

    async def _post_data_check(self, info, data: Dict[str, object], action=A.WRITE):
        # 写入/插入权限检查
        if action == A.WRITE:
            new_data = {}
            for k, v in data.items():
                k: str
                # k 中要存在. 但排除掉列名就是 xxx.xx 的情况
                if '.' in k and not k in self.fields:
                    k, op = k.rsplit('.', 1)
                    v = UpdateInfo(k, 'incr', v)
                new_data[k] = v
            data = new_data

        data = dict_filter(data, self.fields.keys())
        if len(data) == 0: return self.finish(RETCODE.INVALID_POSTDATA)
        logger.debug('request permission: [%s] of table %r' % (action, self.table_name))

        if action == A.WRITE:
            code, record = await self._sql.select_one(info)
            valid = self.ability.can_with_record(self.current_user, action, record, available=data.keys())
            info.clear_condition()
            info.set_select([self.primary_key])
            info.add_condition(self.primary_key, '==', record.get(self.primary_key))
        else:
            # A.CREATE
            valid = self.ability.can_with_columns(self.current_user, action, self.table_name, data.keys())

        if len(valid) != len(data):
            logger.debug("request permission failed. request / valid: %r, %r" % (list(data.keys()), valid))
            return self.finish(RETCODE.PERMISSION_DENIED)
        else:
            logger.debug("request permission successed: %r" % list(data.keys()))

        return data

    async def set(self):
        info = ParamsQueryInfo.new(self, self.params, self.ability)
        self._check_handle_result(self.handle_query(info))
        if self.is_finished: return

        raw_post = await self.post_data()
        values = await self._post_data_check(info, raw_post, A.WRITE)
        if self.is_finished: return
        self._check_handle_result(await async_call(self.before_update, raw_post, values))
        if self.is_finished: return

        logger.debug('set data: %s' % values)
        code, data = await self._sql.update(info, values)
        if code == RETCODE.SUCCESS:
            await async_call(self.after_update, data)
        self.finish(code, data)

    async def new(self):
        raw_post = await self.post_data()
        values = await self._post_data_check(None, raw_post, action=A.CREATE)
        logger.debug('new data: %s' % values)
        if self.is_finished: return
        self._check_handle_result(self.before_insert(raw_post, values))
        if self.is_finished: return

        code, data = await self._sql.insert(values)
        if code == RETCODE.SUCCESS:
            data = self._filter_record_by_ability(data)
            if not data:
                logger.warning("nothing returns after record created, did you set proper permissions?")
                return self.finish(RETCODE.SUCCESS, {})
            self._check_handle_result(await async_call(self.after_read, data))
            self._check_handle_result(await async_call(self.after_insert, raw_post, data))
            if self.is_finished: return
        self.finish(code, data)

    def do_delete(self, info: ParamsQueryInfo):
        """
        overwrite it if you need
        :param info:
        :return:
        """
        n = self._sql.delete(info)
        self.finish(RETCODE.SUCCESS, n)

    async def delete(self):
        info = ParamsQueryInfo.new(self, self.params, self.ability)
        self._check_handle_result(await async_call(self.handle_query, info))
        if self.is_finished: return

        logger.debug('request permission: [%s] of table %r' % (A.DELETE, self.table_name))
        code, record = await self._sql.select_one(info)
        valid = self.ability.can_with_record(self.current_user, A.DELETE, record, available=record.keys())
        info.clear_condition()
        info.set_select([self.primary_key])
        info.add_condition(self.primary_key, '==', record.get(self.primary_key))

        if len(valid) == len(record.keys()):
            logger.debug("request permission successed: %r" % list(record.keys()))
            code, data = await self.do_delete(info)
            self.finish(code, data)
        else:
            self.finish(RETCODE.PERMISSION_DENIED)
            logger.debug("request permission failed. valid / requested: %r, %r" % (valid, list(record.keys())))

    @staticmethod
    @abstractmethod
    async def _fetch_fields(cls_or_self):
        """
        4 values must be set up in this function:
        1. cls_or_self.table_name: str
        2. cls_or_self.fields: Dict['column', Any]
        3. cls_or_self.primary_key: str
        4. cls_or_self.foreign_keys: Dict['column', ['foreign table name']]

        :param cls_or_self:
        :return:
        """
        pass

    async def handle_query(self, info: ParamsQueryInfo) -> Union[None, tuple]:
        pass

    async def after_read(self, values: Dict) -> Union[None, tuple]:
        pass

    async def before_insert(self, raw_post: Dict, values: Dict) -> Union[None, tuple]:
        pass

    async def after_insert(self, raw_post: Dict, values: Dict) -> Union[None, tuple]:
        """ Emitted before finish, no more filter """
        pass

    async def before_update(self, raw_post: Dict, values: Dict) -> Union[None, tuple]:
        """ raw_post 权限过滤和列过滤前，values 过滤后 """
        pass

    async def after_update(self, values: Dict):
        pass
