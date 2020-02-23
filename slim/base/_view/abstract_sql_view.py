import logging
from abc import abstractmethod
from enum import Enum
from typing import Tuple, Union, Dict, Iterable, Type, List, Set, Any, Optional

import schematics
from aiohttp.web_request import BaseRequest, FileField
from schematics.types import BaseType
from .base_view import BaseView
from .err_catch_context import ErrorCatchContext
from .view_options import ViewOptions
from slim.exception import SlimException, PermissionDenied, FinishQuitException, InvalidParams, RecordNotFound, \
    InvalidRole

from slim.base.sqlquery import SQLQueryInfo, SQLForeignKey, SQLValuesToWrite, ALL_COLUMNS, PRIMARY_KEY, SQL_OP
from slim.base.app import Application
from slim.base.permission import Permissions, Ability, BaseUser, A, DataRecord
from slim.base.sqlfuncs import AbstractSQLFunctions
from slim.retcode import RETCODE
from slim.utils.cls_property import classproperty
from slim.utils import pagination_calc, async_call, get_ioloop, get_class_full_name

logger = logging.getLogger(__name__)


class InnerInterfaceName:
    GET = 'get'
    LIST = 'list'
    SET = 'set'
    NEW = 'new'
    DELETE = 'delete'


class AbstractSQLView(BaseView):
    _sql_cls = AbstractSQLFunctions
    is_base_class = True  # skip cls_init check

    options_cls = ViewOptions
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小，若为-1取出所有
    LIST_PAGE_SIZE_CLIENT_LIMIT = None  # None 为与LIST_PAGE_SIZE相同，-1 为无限
    LIST_ACCEPT_SIZE_FROM_CLIENT = False

    table_name: str = None
    primary_key: str = None
    data_model: Type[schematics.Model] = None

    foreign_keys: Dict[str, List[SQLForeignKey]] = {}
    foreign_keys_table_alias: Dict[str, str] = {}  # to hide real table name

    @classproperty
    def fields(cls) -> Dict[str, BaseType]:  # OrderedDict
        return cls.data_model.fields

    @classmethod
    def _is_skip_check(cls):
        skip_check = False
        if 'is_base_class' in cls.__dict__:
            skip_check = getattr(cls, 'is_base_class')
        return skip_check

    @classmethod
    def interface_register(cls):
        super().interface_register()

        cls._use('get', 'GET', _sql_query=True, summary='获取单项', _inner_name=InnerInterfaceName.GET)
        cls._use_lst('list', _sql_query=True, summary='获取列表', _inner_name=InnerInterfaceName.LIST)
        cls._use('set', 'POST', _sql_query=True, _sql_post=True, summary='写入', _inner_name=InnerInterfaceName.SET)
        cls._use('update', 'POST', _sql_query=True, _sql_post=True, _inner_name=InnerInterfaceName.SET)
        cls._use('new', 'POST', _sql_post=True, summary='新建', _inner_name=InnerInterfaceName.NEW)
        cls._use('delete', 'POST', _sql_query=True, summary='删除', _inner_name=InnerInterfaceName.DELETE)

    @classmethod
    def add_soft_foreign_key(cls, column, table_name, alias=None):
        """
        Add a soft foreign key instead of a real one to avoid constraint problem.
        The `column` should store value of `table_name`'s primary key.

        :param column: table's column
        :param table_name: target table name
        :param alias: table name's alias. Default is as same as table name.
        :return: True, None
        """
        if column in cls.fields:
            table = SQLForeignKey(table_name, column, True)

            if alias:
                if alias in cls.foreign_keys_table_alias:
                    logger.warning("The alias of table is already exists, overwriting: %s.%s to %s" %
                                   (get_class_full_name(cls), column, table_name))
                cls.foreign_keys_table_alias[alias] = table

            if column not in cls.foreign_keys:
                cls.foreign_keys[column] = [table]
            else:
                if not alias:
                    logger.warning("An alias is required for the soft foreign key: %s.%s to %r" %
                                   (get_class_full_name(cls), column, table_name))
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

        cls_full_name = get_class_full_name(cls)
        assert isinstance(cls.LIST_PAGE_SIZE, int), '%s.LIST_PAGE_SIZE must be int' % cls_full_name
        assert cls.LIST_PAGE_SIZE == -1 or cls.LIST_PAGE_SIZE > 0, \
            '%s.LIST_PAGE_SIZE must be -1 or more than 0' % cls_full_name
        assert cls.LIST_PAGE_SIZE_CLIENT_LIMIT is None or isinstance(cls.LIST_PAGE_SIZE_CLIENT_LIMIT, int), \
            '%s.LIST_PAGE_SIZE_CLIENT_LIMIT must be None or int' % cls_full_name
        if isinstance(cls.LIST_PAGE_SIZE_CLIENT_LIMIT, int):
            assert cls.LIST_PAGE_SIZE_CLIENT_LIMIT == -1 or cls.LIST_PAGE_SIZE_CLIENT_LIMIT > 0, \
                '%s.LIST_PAGE_SIZE must be None or -1 or more than 0' % cls_full_name

        async def func():
            await cls._fetch_fields(cls)
            if not cls._is_skip_check():
                assert cls.table_name
                assert cls.data_model
                # assert cls.fields
                # assert cls.primary_key
                # assert cls.foreign_keys

        get_ioloop().run_until_complete(func())

    def _load_role(self, role):
        # TODO: 当未继承自UserView的时候给出不同的提示
        user = self.current_user if self.can_get_user else None
        self.ability = self.permission.request_role(user, role)
        return self.ability

    @property
    def current_request_role(self) -> Optional[Union[int, str]]:
        """
        Current role requesting by client.
        :return:
        """
        role_val = self.headers.get('Role', None)
        if role_val is not None:
            return int(role_val) if role_val.isdigit() else role_val

    def __init__(self, app: Application, aiohttp_request: BaseRequest = None):
        super().__init__(app, aiohttp_request)
        self._sql = None
        self.current_interface = None

    async def _prepare(self):
        await super()._prepare()
        # _sql 里使用了 self.err 存放数据
        # 那么可以推测在并发中，cls._sql.err 会被多方共用导致出错
        self._sql = self._sql_cls(self.__class__)
        if not self._load_role(self.current_request_role):
            logger.debug("load role %r failed, please check permission settings of View %r"
                         " (mapping to table %r)." %
                         (self.current_request_role, type(self).__name__, type(self).table_name))
            raise InvalidRole(self.current_request_role)

    async def load_fk(self, info: SQLQueryInfo, records: Iterable[DataRecord]) -> Union[List, Iterable]:
        """
        :param info:
        :param records: the data got from database and filtered from permission
        :return:
        """

        # if not items, items is probably [], so return itself.
        # if not items: return items

        # 1. get tables' instances
        # table_map = {}
        # for column in info['loadfk'].keys():
        #     tbl_name = self.foreign_keys[column][0]
        #     table_map[column] = self.app.tables[tbl_name]

        # 2. get query parameters
        async def check(data, records):
            for column, fkvalues_lst in data.items():
                for fkvalues in fkvalues_lst:
                    # got nothing, skip
                    if not records:
                        continue

                    pks = []
                    all_ni = True

                    for i in records:
                        val = i.get(column, NotImplemented)
                        if val != NotImplemented:
                            all_ni = False
                        pks.append(val)

                    if all_ni:
                        logger.debug("load foreign key failed, do you have read permission to the column %r?" % column)
                        continue

                    # 3. query foreign keys
                    vcls = self.app.tables[fkvalues['table']]
                    v = vcls(self.app, self._request)  # fake view
                    await v._prepare()
                    info2 = SQLQueryInfo()
                    info2.set_select(ALL_COLUMNS)
                    info2.add_condition(PRIMARY_KEY, SQL_OP.IN, pks)
                    info2.bind(v)

                    # ability = vcls.permission.request_role(self.current_user, fkvalues['role'])
                    # info2.check_query_permission_full(self.current_user, fktable, ability)

                    try:
                        fk_records, count = await v._sql.select_page(info2, size=-1)
                    except RecordNotFound:
                        # 外键没有找到值，也许全部都是null，这很常见
                        continue

                    # if not fk_records: continue
                    await v.check_records_permission(info2, fk_records)

                    fk_dict = {}
                    for i in fk_records:
                        # 主键: 数据
                        fk_dict[i[vcls.primary_key]] = i

                    column_to_set = fkvalues.get('as', column) or column
                    for _, record in enumerate(records):
                        k = record.get(column, NotImplemented)
                        if k in fk_dict:
                            record[column_to_set] = fk_dict[k]

                    if fkvalues['loadfk']:
                        await check(fkvalues['loadfk'], fk_records)

        await check(info.loadfk, records)
        return records

    async def _call_handle(self, func, *args):
        """ call and check result of handle_query/read/insert/update """
        await async_call(func, *args)

        if self.is_finished:
            raise FinishQuitException()

    def _get_list_page_and_size(self) -> Tuple[int, int]:
        page = self.route_info.get('page', '1').strip()

        if not page.isdigit():
            raise InvalidParams("`page` is not a number")
        page = int(page)

        client_size = self.route_info.get('size', '').strip()
        if self.LIST_ACCEPT_SIZE_FROM_CLIENT and client_size:
            page_size_limit = self.LIST_PAGE_SIZE_CLIENT_LIMIT or self.LIST_PAGE_SIZE
            if client_size == '-1':  # -1 means all
                client_size = -1
            elif client_size.isdigit():  # size >= 0
                client_size = int(client_size)
                if client_size == 0:
                    # use default value
                    client_size = page_size_limit
                else:
                    if page_size_limit != -1:
                        client_size = min(client_size, page_size_limit)
            else:
                raise InvalidParams("`size` is not a number")
        else:
            client_size = self.LIST_PAGE_SIZE

        return page, client_size

    async def check_records_permission(self, info, records, *, exception_cls: Type[SlimException]=PermissionDenied):
        user = self.current_user if self.can_get_user else None
        for record in records:
            columns = record.set_info(info, self.ability, user)
            if not columns: raise exception_cls(self.table_name)
        await self._call_handle(self.after_read, records)

    async def get(self):
        self.current_interface = InnerInterfaceName.GET
        with ErrorCatchContext(self):
            info = SQLQueryInfo(self.params, view=self)
            await self._call_handle(self.before_query, info)
            record = await self._sql.select_one(info)

            if record:
                records = [record]
                # , exception_cls=RecordNotFound
                await self.check_records_permission(info, records)
                data_dict = await self.load_fk(info, records)
                self.finish(RETCODE.SUCCESS, data_dict[0])
            else:
                self.finish(RETCODE.NOT_FOUND)

    async def list(self):
        self.current_interface = InnerInterfaceName.LIST
        with ErrorCatchContext(self):
            page, size = self._get_list_page_and_size()
            info = SQLQueryInfo(self.params, view=self)
            await self._call_handle(self.before_query, info)
            records, count = await self._sql.select_page(info, size, page)
            await self.check_records_permission(info, records)

            if size == -1:
                size = count if count != 0 else 1

            pg = pagination_calc(count, size, page)
            records = await self.load_fk(info, records)
            pg["items"] = records

            self.finish(RETCODE.SUCCESS, pg)

    async def update(self):
        self.current_interface = InnerInterfaceName.SET
        with ErrorCatchContext(self):
            info = SQLQueryInfo(self.params, self)
            raw_post = await self.post_data()

            await self._call_handle(self.before_query, info)
            record = await self._sql.select_one(info)

            if record:
                records = [record]
                values = SQLValuesToWrite(raw_post)
                values.bind(self, A.WRITE, records)
                await self._call_handle(self.before_update, raw_post, values, records)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('update record(s): %s' % values)

                # 注：此处returning为true是因为后续要检查数据的权限，和前端要求无关
                new_records = await self._sql.update(records, values, returning=True)
                await self.check_records_permission(None, new_records)
                await self._call_handle(self.after_update, raw_post, values, records, new_records)
                if values.returning:
                    self.finish(RETCODE.SUCCESS, new_records[0])
                else:
                    self.finish(RETCODE.SUCCESS, len(new_records))
            else:
                self.finish(RETCODE.NOT_FOUND)

    set = update

    async def new(self, values: SQLValuesToWrite = None):
        self.current_interface = InnerInterfaceName.NEW
        with ErrorCatchContext(self):
            raw_post = await self.post_data()
            values = SQLValuesToWrite(raw_post, self, A.CREATE)
            values_lst = [values]

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('insert record(s): %s' % values_lst)
            # 注意，这里只给一个，new接口暂不支持一次insert多个
            await self._call_handle(self.before_insert, raw_post, values)

            values.validate_before_execute_insert(self)
            records = await self._sql.insert(values_lst, returning=True)
            await self.check_records_permission(None, records)
            await self._call_handle(self.after_insert, raw_post, values_lst[0], records[0])

            if values.returning:
                self.finish(RETCODE.SUCCESS, records[0])
            else:
                self.finish(RETCODE.SUCCESS, len(records))

    async def delete(self):
        self.current_interface = InnerInterfaceName.DELETE
        with ErrorCatchContext(self):
            info = SQLQueryInfo(self.params, self)
            await self._call_handle(self.before_query, info)
            record = await self._sql.select_one(info)

            if record:
                records = [record]
                user = self.current_user if self.can_get_user else None
                logger.debug('request permission as %r: [%s] of table %r' % (self.ability.role, A.DELETE, self.table_name))
                for record in records:
                    valid = self.ability.can_with_record(user, A.DELETE, record, available=record.keys())

                    if len(valid) == len(record.keys()):
                        logger.debug("request permission successed as %r: %r" % (self.ability.role, list(record.keys())))
                    else:
                        logger.debug(
                            "request permission failed as %r. valid / requested: %r, %r" % (self.ability.role, valid, list(record.keys())))
                        return self.finish(RETCODE.PERMISSION_DENIED)

                await self._call_handle(self.before_delete, records)
                num = await self._sql.delete(records)
                await self._call_handle(self.after_delete, records)
                self.finish(RETCODE.SUCCESS, num)
            else:
                self.finish(RETCODE.NOT_FOUND)

    @staticmethod
    @abstractmethod
    async def _fetch_fields(cls_or_self):
        """
        4 values must be set up in this function:
        1. cls.table_name: str
        2. cls.primary_key: str
        3. cls.data_model: Type[schematics.Model]
        4. cls.foreign_keys: Dict['column', List[SQLForeignKey]]

        :param cls_or_self:
        :return:
        """
        pass

    async def before_query(self, info: SQLQueryInfo):
        pass

    async def after_read(self, records: List[DataRecord]):
        """
        一对多，当有一个权限检查失败时即返回异常
        :param records:
        :return:
        """
        pass

    async def before_insert(self, raw_post: Dict, values: SQLValuesToWrite):
        """
        一对一
        :param raw_post:
        :param values:
        :return:
        """
        pass

    async def after_insert(self, raw_post: Dict, values: SQLValuesToWrite, record: DataRecord):
        """
        一对一
        Emitted before finish
        :param raw_post:
        :param values:
        :param record:
        :return:
        """
        pass

    async def before_update(self, raw_post: Dict, values: SQLValuesToWrite, records: List[DataRecord]):
        """
        一对多，当有一个权限检查失败时即返回异常
        raw_post 权限过滤和列过滤前，values 过滤后
        :param raw_post:
        :param values:
        :param records:
        :return:
        """
        pass

    async def after_update(self, raw_post: Dict, values: SQLValuesToWrite,
                           old_records: List[DataRecord], records: List[DataRecord]):
        """
        :param old_records:
        :param raw_post:
        :param values:
        :param records:
        :return:
        """

    async def before_delete(self, records: List[DataRecord]):
        """
        :param records:
        :return:
        """
        pass

    async def after_delete(self, deleted_records: List[DataRecord]):
        """
        :param deleted_records:
        :return:
        """
        pass
