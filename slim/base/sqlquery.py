import json
import logging
from enum import Enum
from typing import Union, Iterable, List, TYPE_CHECKING, Dict, Set

from ..utils import blob_converter, json_converter, MetaClassForInit, is_py36, dict_filter, dict_filter_inplace
from ..exception import SyntaxException, ResourceException, InvalidParams, \
    PermissionDenied, ColumnNotFound, ColumnIsNotForeignKey, SQLOperatorInvalid, RoleNotFound, SlimException, \
    InvalidPostData

if TYPE_CHECKING:
    from .view import AbstractSQLView
    from .permission import Ability
    from .user import BaseUser


logger = logging.getLogger(__name__)


class SQL_TYPE(Enum):
    INT = int
    FLOAT = float
    STRING = str
    BOOLEAN = bool
    BLOB = blob_converter
    JSON = json_converter


PRIMARY_KEY = object() # for add condition
ALL_COLUMNS = object()


class DataRecord:
    def __init__(self, table_name, val):
        self.table = table_name
        self.val = val
        self.selected = ALL_COLUMNS
        self.available_columns = ALL_COLUMNS
        self._cache = None

    def _to_dict(self) -> Dict:
        raise NotImplementedError()

    def set_info(self, info: "SQLQueryInfo", ability: "Ability", user: "BaseUser"):
        from .permission import A
        if info:
            self.selected = info.select
        self.available_columns = ability.can_with_record(user, A.READ, self)
        return self.available_columns

    @property
    def cache(self) -> Dict:
        if self._cache is None:
            self._cache = self._to_dict()
        return self._cache

    def get(self, key, default=None):
        return self.cache.get(key, default)

    def to_dict(self):
        return self.cache

    def keys(self):
        return self.cache.keys()

    def pop(self, key):
        return self.cache.pop(key)

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        self.cache[key] = value

    def __delitem__(self, key):
        self.pop(key)

    def __repr__(self):
        return self.to_dict().__repr__()


class SQLForeignKey:
    def __init__(self, rel_table: str, rel_field: str, rel_type: SQL_TYPE, is_soft_key=False):
        self.rel_table = rel_table
        self.rel_field = rel_field
        self.rel_type = rel_type
        self.is_soft_key = is_soft_key


class SQLQueryOrder:
    def __init__(self, column, order):
        assert order in ('asc', 'desc')
        self.column = column
        self.order = order

    def __eq__(self, other):
        if isinstance(other, SQLQueryOrder):
            return self.column == other.column and self.order == other.order
        return False

    def __repr__(self):
        return '<SQLQueryOrder %r.%s>' % (self.column, self.order)


class SQL_OP(Enum):
    EQ = ('eq', '==', '=')
    NE = ('ne', '!=', '<>')
    LT = ('lt', '<')
    LE = ('le', '<=')
    GE = ('ge', '>=')
    GT = ('gt', '>')
    IN = ('in',)
    IS = ('is',)
    IS_NOT = ('isnot',)
    AND = ('and',)
    OR = ('or',)

    ALL = set(EQ + NE + LT + LE + GE + GT + IN + IS + IS_NOT)


SQL_OP.txt2op = {}
for i in SQL_OP:
    if i == SQL_OP.ALL: continue
    for opval in i.value:
        SQL_OP.txt2op[opval] = i


class QueryConditions(list):
    """ 查询条件，这是ParamsQueryInfo的一部分。与 list 实际没有太大不同，独立为类型的目的是使其能与list区分开来 """
    def __contains__(self, item):
        for i in self:
            if i[0] == item:
                return True

    def map(self, key, func):
        for i in self:
            if i[0] == key:
                i[:] = func(i)


class SQLQueryInfo:
    """ SQL查询参数。"""
    def __init__(self, params=None, view=None):
        if is_py36:
            self.select: Union[List[str], object]
            self.orders: List[SQLQueryOrder]
            self.loadfk: Dict[str, List[Dict[str, object]]]

        self.select = ALL_COLUMNS
        self.conditions = QueryConditions()
        self.orders = []
        self.loadfk = {}

        if params: self.parse(params)
        if view: self.bind(view)

    def set_orders(self, orders: List[SQLQueryOrder]):
        assert isinstance(orders, list)
        for i in orders:
            assert isinstance(i, SQLQueryOrder)
        self.orders = orders.copy()

    @staticmethod
    def parse_order(text):
        """
        :param text: order=id.desc, xxx.asc
        :return: [
            [<column>, asc|desc|default],
            [<column2>, asc|desc|default],
        ]
        """
        orders = []
        for i in map(str.strip, text.split(',')):
            items = i.split('.', 2)

            if len(items) == 1: column, order = items[0], 'default'
            elif len(items) == 2: column, order = items
            else: raise SyntaxException("Invalid order syntax")

            order = order.lower()
            if order not in ('asc', 'desc', 'default'):
                raise SyntaxException('Invalid order mode: %s' % order)

            if order != 'default':
                orders.append(SQLQueryOrder(column, order))
        return orders

    def set_select(self, items):
        if items == ALL_COLUMNS:
            self.select = ALL_COLUMNS
        elif isinstance(items, Iterable):
            for i in items:
                assert isinstance(i, str)
            self.select = set(items)
        else:
            raise SyntaxException('Invalid select')

    @classmethod
    def parse_select(cls, text: str) -> Set:
        """
        get columns from select text
        :param text: col1, col2
        :return: ALL_COLUMNS or ['col1', 'col2']
        """
        if text == '*':
            return ALL_COLUMNS  # None means ALL
        selected_columns = set(filter(lambda x: x, map(str.strip, text.split(','))))
        if not selected_columns:
            raise SyntaxException("No column(s) selected")
        return selected_columns

    @staticmethod
    def parse_load_fk(value: str) -> Dict[str, List[Dict[str, object]]]:
        """
        :param value:{
            <column>: role,
            <column2>: role,
            <column>: {
                'role': role,
                'loadfk': { ... },
            },
        :return: {
            <column>: {
                'role': role,
            },
            ...
            <column3>: {
                'role': role,
                'loadfk': { ... },
            },
        }
        """
        try:
            value = json.loads(value) # [List, Dict[str, str]]
        except json.JSONDecodeError:
            raise SyntaxException('Invalid json syntax for "loadfk": %s' % value)

        if isinstance(value, List):
            new_value = {}
            for i in value:
                new_value[i] = None
            value = new_value
        else:
            raise SyntaxException('Invalid syntax for "loadfk": %s' % value)

        # 标准化 loadfk
        def rebuild(column, data):
            # data: str, role name
            # dict, {'role': <str>, 'as': <str>}
            if isinstance(data, str):
                data = {'role': data, 'as': None, 'table': None, 'loadfk': None}
            elif isinstance(data, dict):
                def check(k, v):
                    if k not in ('role', 'as', 'table', 'loadfk'):
                        return

                    if k == 'as': return v is None or isinstance(v, str)
                    if k == 'table': return v is None or isinstance(v, str)
                    if k == 'loadfk': return v is None or isinstance(v, dict)

                data = [v for k, v in data.items() if check(k ,v)]

            # 递归外键读取
            if data['loadfk']:
                data['loadfk'] = translate(data['loadfk'])
            return data

        def translate(value) -> Dict[str, List[Dict[str, object]]]:
            for column, items in value.items():
                ret = []
                if not isinstance(items, Iterable):
                    items = [items]

                for i in items:
                    ret.append(rebuild(column, i))

                value[column] = ret
            return value

        return translate(value)

    def add_condition(self, field_name, op_name, value):
        """
        Add a query condition and validate it.
        raise ParamsException if failed.
        self.view required
        :param field_name:
        :param op_name:
        :param value:
        :return: None
        """
        if op_name not in SQL_OP.txt2op:
            raise SQLOperatorInvalid(op_name)
        op = SQL_OP.txt2op.get(op_name)
        self.conditions.append([field_name, op, value])  # 注意，必须是list

    def clear_condition(self):
        self.conditions.clear()

    def parse(self, params):
        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]
            if field_name == 'order':
                self.orders = self.parse_order(value)
                continue
            elif field_name == 'select':
                self.select = self.parse_select(value)
                continue
            elif field_name == 'loadfk':
                self.loadfk = self.parse_load_fk(value)
                continue

            op = info[1] if len(info) > 1 else '='
            self.add_condition(field_name, op, value)

    def check_query_permission(self, view: "AbstractSQLView"):
        return self.check_query_permission_full(view.current_user, view.table_name, view.ability)

    def check_query_permission_full(self, user: "BaseUser", table: str, ability: "Ability"):
        from .permission import A

        # QUERY 权限检查，通不过则报错
        checking_columns = []
        for field_name, op, value in self.conditions:
            checking_columns.append(field_name)

        if checking_columns and not ability.can_with_columns(user, A.QUERY, table, checking_columns):
            raise PermissionDenied("None of these columns had permission to %r: %r" % (A.QUERY, checking_columns))

        # READ 权限检查，通不过时将其过滤
        checking_columns = self.loadfk.keys()  # 外键过滤
        new_loadfk = ability.can_with_columns(user, A.READ, table, checking_columns)
        self.loadfk = dict_filter(self.loadfk, new_loadfk)

        new_select = ability.can_with_columns(user, A.READ, table, self.select)  # select 过滤
        self.set_select(new_select)

    def bind(self, view: "AbstractSQLView"):
        def check_column_exists(column):
            if column is PRIMARY_KEY:
                return
            if field_name not in view.fields:
                raise ColumnNotFound(field_name)

        # select check
        if self.select is ALL_COLUMNS:
            self.select = view.fields.keys()
        else:
            for i, field_name in enumerate(self.select):
                check_column_exists(field_name)
                if field_name == PRIMARY_KEY:
                    if not isinstance(self.select, List):
                        self.select = list(self.select)
                    self.select[i] = view.primary_key

        # where check
        for i in self.conditions:
            field_name, op, value = i
            check_column_exists(field_name)
            if field_name == PRIMARY_KEY:
                i[0] = field_name = view.primary_key
            field_type = view.fields[field_name]
            try:
                # 注：外键的类型会是其指向的类型，这里不用担心
                if op in (SQL_OP.IN, ):
                    assert isinstance(value, Iterable)
                    i[2] = list(map(field_type.value, value))
                else:
                    i[2] = field_type.value(value)
            except:
                raise SlimException("bad value")

        # order check
        for i, od in enumerate(self.orders):
            check_column_exists(od.column)
            if od.column == PRIMARY_KEY:
                self.orders[i] = view.primary_key

        # foreign key check
        app = view.app

        def check_loadfk_data(the_view, data):
            if PRIMARY_KEY in data:
                data[the_view.primary_key] = data[PRIMARY_KEY]
                del data[PRIMARY_KEY]

            for field_name, data_lst in data.items():
                # [{'role': role, 'loadfk': {...}}]
                # [{'as': 's24h', 'table': 's24', 'role': role}]

                # 检查列是否存在
                if field_name not in the_view.fields:
                    raise ColumnNotFound(field_name)

                field_type = view.fields[field_name]
                # 检查列是否是合法的外键列
                fks = the_view.foreign_keys.get(field_name, None)
                if not fks: raise ColumnIsNotForeignKey(field_name)

                for data in data_lst:
                    # 检查是否采用别名将外键对应到特定表上
                    if data['table']:
                        if data['table'] not in the_view.foreign_keys_table_alias:
                            raise ResourceException('Foreign key not match the table: %s -> %s' % (field_name, data['table']))
                        fk = the_view.foreign_keys_table_alias[data['table']]
                    else:
                        fk = fks[0] # 取第一个结果（即默认外键）

                    # 检查对应的表的角色是否存在
                    if data['role'] not in app.permissions[fk.rel_table].roles:
                        raise RoleNotFound('%s of %s' % (data['role'], fk.rel_table))

                    # 递归外键读取
                    if data['loadfk']:
                        check_loadfk_data(app.tables[fk.rel_table], data)

        if self.loadfk:
            check_loadfk_data(view, self.loadfk)

        # permission check
        # 是否需要一个 order 权限？
        if view.ability:
            self.check_query_permission(view)


class UpdateInfo:
    def __init__(self, key, op, val):
        assert op in ('incr', 'to')
        self.key = key
        self.op = op
        self.val = val


class SQLValuesToWrite(dict):
    def __init__(self, post_data=None):
        if post_data:
            self.parse(post_data)
        super().__init__()

    def parse(self, post_data):
        self.clear()
        for k, v in post_data.items():
            if '.' in k:
                k, op = k.rsplit('.', 1)
                v = UpdateInfo(k, 'incr', v)
            self[k] = v

    def check_query_permission(self, view: "AbstractSQLView", action, records=None):
        return self.check_query_permission_full(view.current_user, view.table_name, view.ability, action, records)

    def check_query_permission_full(self, user: "BaseUser", table: str, ability: "Ability", action, records=None):
        from .permission import A
        logger.debug('request permission: [%s] of table %r' % (action, table))

        if action == A.WRITE:
            for record in records:
                valid = ability.can_with_record(user, action, record, available=self.keys())
                if len(valid) != len(self):
                    logger.debug("request permission failed. request / valid: %r, %r" % (list(self.keys()), valid))
                    raise PermissionDenied()
        elif action == A.CREATE:
            valid = ability.can_with_columns(user, action, table, self.keys())

            if len(valid) != len(self):
                logger.debug("request permission failed. request / valid: %r, %r" % (list(self.keys()), valid))
                raise PermissionDenied()
        else:
            raise SlimException("Invalid action to write: %r" % action)

        logger.debug("request permission successed: %r" % list(self.keys()))

    def bind(self, view: "AbstractSQLView", action=None, records=None):
        dict_filter_inplace(self, view.fields.keys())
        if len(self) == 0:
            raise InvalidPostData()

        for k, v in self.items():
            field_type = view.fields[k]
            try:
                if isinstance(v, UpdateInfo):
                    if v.op == 'to':
                        self[k] = field_type.value(v)
                    elif v.op == 'incr':
                        v.val = field_type.value(v)
                else:
                    self[k] = field_type.value(v)
            except:
                raise SlimException("bad value")

        if action:
            self.check_query_permission(view, action, records)
