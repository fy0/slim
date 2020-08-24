import json
import logging
from abc import abstractmethod
from typing import Tuple, Union, Dict, Iterable, Type, List, Optional, Mapping

import schematics
from multidict import istr
from schematics.types import BaseType

from slim.base.types import BuiltinInterface
from .base_view import BaseView
from ..web import ASGIRequest
from .err_catch_context import ErrorCatchContext
from .view_options import SQLViewOptions
from slim.exception import SlimException, PermissionDenied, FinishQuitException, InvalidParams, RecordNotFound, \
    InvalidRole, InvalidPostData

from slim.base.sqlquery import SQLQueryInfo, SQLForeignKey, SQLValuesToWrite, ALL_COLUMNS, PRIMARY_KEY, SQL_OP
from slim.base.app import Application
from slim.base.permission import A, DataRecord
from slim.base.sqlfuncs import AbstractSQLFunctions
from slim.retcode import RETCODE
from slim.utils.cls_property import classproperty
from slim.utils import pagination_calc, async_call, get_ioloop, get_class_full_name
from ..route import Route

logger = logging.getLogger(__name__)


class AbstractSQLView(BaseView):
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小，若为-1取出所有
    LIST_PAGE_SIZE_CLIENT_LIMIT = None  # None 为与LIST_PAGE_SIZE相同，-1 为无限
    LIST_ACCEPT_SIZE_FROM_CLIENT = False  # 是否允许客户端指定 page size

    options_cls = SQLViewOptions
    _sql_cls = AbstractSQLFunctions
    is_base_class = True  # skip cls_init check

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
        pass

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
        if options and isinstance(options, SQLViewOptions):
            options.assign(cls)

    @classmethod
    def cls_init(cls, check_options=True):
        if check_options:
            cls._check_view_options()

        # because of BaseView.cls_init is a bound method (@classmethod)
        # so we can only route BaseView._interface, not cls._interface defined by user
        BaseView.cls_init.__func__(cls)
        super().cls_init()  # fixed in 3.6

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

    def bulk_num(self):
        bulk_key = istr('Bulk')
        if bulk_key in self.headers:
            try:
                num = int(self.headers.get(bulk_key))
                if num <= 0:
                    # num invalid
                    return 1
                return num
            except ValueError:
                pass
            return -1
        return 1

    async def is_returning(self) -> bool:
        key = 'returning'
        if istr(key) in self.headers:
            return True
        post = await self.post_data()
        if isinstance(post, Mapping) and key in post:
            return True
        return key in self.params

    @property
    def current_request_role(self) -> Optional[str]:
        """
        Current role requesting by client.
        :return:
        """
        return self.headers.get(istr('Role'), None)

    def __init__(self, app: Application = None, req: ASGIRequest = None):
        super().__init__(app, req)
        self._sql = None
        self.current_interface = None

    @classmethod
    def _on_bind(cls, route: Route):
        super()._on_bind(route)

        # register interface
        route.get(summary='获取单项')(cls.get)
        route.get(summary='获取列表', url='list/:page/:size?')(cls.list)
        route.post(summary='更新')(cls.set)
        route.post(summary='新建')(cls.new)
        route.post(summary='新建(批量)')(cls.bulk_insert)
        route.post(summary='删除')(cls.delete)

        cls.get._route_info.builtin_interface = BuiltinInterface.GET
        cls.list._route_info.builtin_interface = BuiltinInterface.LIST
        cls.set._route_info.builtin_interface = BuiltinInterface.SET
        cls.new._route_info.builtin_interface = BuiltinInterface.NEW
        cls.bulk_insert._route_info.builtin_interface = BuiltinInterface.BULK_INSERT
        cls.delete._route_info.builtin_interface = BuiltinInterface.DELETE

        if cls.interface_register != AbstractSQLView.interface_register:
            # TODO: deprecated?
            pass
        cls.interface_register()

    async def _prepare(self):
        await super()._prepare()

        # _sql 里使用了 self.err 存放数据
        # 那么可以推测在并发中，cls._sql.err 会被多方共用导致出错
        self._sql = self._sql_cls(self.__class__)
        if not self._load_role(self.current_request_role):
            user = self.current_user if self.can_get_user else None
            logger.debug("load role %r failed, please check permission settings of View %r"
                         " (mapping to table %r). current user id: %r" %
                         (self.current_request_role, type(self).__name__, type(self).table_name, user.id if user else None))
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
                    v = vcls(self.app, self.request)  # fake view
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

                    if not fk_records: continue
                    fk_records = list(fk_records)
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

    def _parse_sql_query(self):
        return SQLQueryInfo(view=self)

    def _get_list_page_and_size(self, page, client_size) -> Tuple[int, int]:
        page = page.strip()

        if not page.isdigit():
            raise InvalidParams("`page` is not a number")
        page = int(page)

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

    async def check_records_permission(self, info, records, *, exception_cls: Type[SlimException] = PermissionDenied):
        user = self.current_user if self.can_get_user else None
        for record in records:
            columns = record.set_info(info, self.ability, user)
            if not columns: raise exception_cls(self.table_name)
        await self._call_handle(self.after_read, records)

    async def get(self):
        """
        获取单项记录接口，查询规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify
        """
        with ErrorCatchContext(self):
            info = await SQLQueryInfo.build(self)
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

    async def list(self, page='1', size=''):
        """
        获取分页记录接口，查询规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify
        """
        with ErrorCatchContext(self):
            page, size = self._get_list_page_and_size(page, size)
            info = await SQLQueryInfo.build(self)
            await self._call_handle(self.before_query, info)
            records, count = await self._sql.select_page(info, page, size)
            # records should be list because after_read maybe change it
            records = list(records)
            await self.check_records_permission(info, records)

            if size == -1:
                size = count if count != 0 else 1

            pg = pagination_calc(count, size, page)
            records = await self.load_fk(info, records)
            pg["items"] = records

            self.finish(RETCODE.SUCCESS, pg)

    async def set(self):
        """
        更新数据接口
        查询规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify
        赋值规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify?id=修改新建
        """
        with ErrorCatchContext(self):
            info = await SQLQueryInfo.build(self)

            await self._call_handle(self.before_query, info)
            records, count = await self._sql.select_page(info, size=self.bulk_num())

            if records:
                # 确保 before_update 时得到list
                records = list(records)
                values = SQLValuesToWrite(await self.post_data())
                values.bind(self, A.WRITE, records)
                await self._call_handle(self.before_update, values, records)

                # 如果 before_update 之后，不再有values，那么抛出invalid_postdata
                if len(values) == 0:
                    raise InvalidPostData("No value to set for table: %s" % self.table_name)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('update record(s): %s' % values)

                # 注：此处returning为true是因为后续要检查数据的权限，和前端要求无关
                new_records = await self._sql.update(records, values, returning=True)
                await self.check_records_permission(None, new_records)
                await self._call_handle(self.after_update, values, records, new_records)
                if await self.is_returning():
                    self.finish(RETCODE.SUCCESS, new_records)
                else:
                    self.finish(RETCODE.SUCCESS, len(new_records))
            else:
                self.finish(RETCODE.NOT_FOUND)

    async def _base_insert(self, raw_values_lst, ignore_exists):
        with ErrorCatchContext(self):
            if isinstance(raw_values_lst, str):
                try:
                    values_lst = json.loads(raw_values_lst)
                    assert isinstance(values_lst, list)
                except (json.JSONDecodeError, AssertionError):
                    return self.finish(RETCODE.INVALID_POSTDATA, "`value_lst` is not validated")

            values_lst = [SQLValuesToWrite(x, self, A.CREATE) for x in raw_values_lst]

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug('insert record(s): %s' % values_lst)

            await self._call_handle(self.before_insert, values_lst)
            for values in values_lst:
                values.validate_before_execute_insert(self)

            records = await self._sql.insert(values_lst, returning=True, ignore_exists=ignore_exists)
            await self.check_records_permission(None, records)
            await self._call_handle(self.after_insert, values_lst, records)
            return records

    async def bulk_insert(self):
        """
        批量新建接口
        赋值规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify?id=修改新建
        """
        post = await self.post_data()
        if not 'items' in post:
            raise InvalidPostData("`items` is required")
        records = await self._base_insert(post['items'], True)
        if self.is_finished:
            return

        if await self.is_returning():
            self.finish(RETCODE.SUCCESS, records)
        else:
            self.finish(RETCODE.SUCCESS, len(records))

    async def new(self):
        """
        新建接口
        赋值规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify?id=修改新建
        """
        raw_post = await self.post_data()
        records = await self._base_insert([raw_post], False)
        if self.is_finished:
            return

        if await self.is_returning():
            self.finish(RETCODE.SUCCESS, records[0])
        else:
            self.finish(RETCODE.SUCCESS, len(records))

    async def delete(self):
        """
        删除记录接口
        查询规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify
        赋值规则参考 https://fy0.github.io/slim/#/quickstart/query_and_modify?id=修改新建
        """
        with ErrorCatchContext(self):
            info = await SQLQueryInfo.build(self)
            await self._call_handle(self.before_query, info)
            records, count = await self._sql.select_page(info, size=self.bulk_num())

            if records:
                records = list(records)
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
        """
        在发生查询时触发。
        触发接口：get list set delete
        :param info:
        :return:
        """
        pass

    async def after_read(self, records: List[DataRecord]):
        """
        触发接口：get list new set
        :param records:
        :return:
        """
        pass

    async def before_insert(self, values_lst: List[SQLValuesToWrite]):
        """
        插入操作之前
        触发接口：new
        :param values_lst:
        :return:
        """
        pass

    async def after_insert(self, values_lst: List[SQLValuesToWrite], records: List[DataRecord]):
        """
        插入操作之后
        触发接口：new
        :param values_lst:
        :param records:
        :return:
        """
        pass

    async def before_update(self, values: SQLValuesToWrite, records: List[DataRecord]):
        """
        触发接口：set
        :param values:
        :param records:
        :return:
        """
        pass

    async def after_update(self, values: SQLValuesToWrite, old_records: List[DataRecord],
                           new_records: List[DataRecord]):
        """
        触发接口：set
        :param values:
        :param old_records:
        :param new_records:
        :return:
        """

    async def before_delete(self, records: List[DataRecord]):
        """
        触发接口：delete
        :param records:
        :return:
        """
        pass

    async def after_delete(self, deleted_records: List[DataRecord]):
        """
        触发接口：delete
        :param deleted_records:
        :return:
        """
        pass
