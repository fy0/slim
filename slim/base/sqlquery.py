import json
import logging
import traceback
from enum import Enum
from typing import Union, Iterable, List, TYPE_CHECKING, Dict, Set
from multidict import MultiDict

from ..utils import BlobParser, JSONParser, is_py36, dict_filter, dict_filter_inplace, BoolParser
from ..exception import SyntaxException, ResourceException, InvalidParams, \
    PermissionDenied, ColumnNotFound, ColumnIsNotForeignKey, SQLOperatorInvalid, InvalidRole, SlimException, \
    InvalidPostData, TableNotFound

if TYPE_CHECKING:
    from .view import AbstractSQLView
    from .permission import Ability
    from .user import BaseUser


logger = logging.getLogger(__name__)


class SQL_TYPE(Enum):
    INT = int
    FLOAT = float
    STRING = str
    BLOB = BlobParser
    BOOLEAN = BoolParser
    JSON = JSONParser


def make_array_parser(sql_type: SQL_TYPE):
    class ArrayParser:
        def __new__(cls, val):
            if isinstance(val, str):
                return list(map(sql_type.value, json.loads(val)))
            if isinstance(val, list):
                return list(map(sql_type.value, val))
            return val
    return ArrayParser


class SQL_TYPE_ARRAY:
    def __init__(self, sql_type):
        self.sql_type = sql_type

    @property
    def value(self):
        return make_array_parser(self.sql_type)


class NamedObject:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Named Object: %s>' % self.name


PRIMARY_KEY = NamedObject('Primary Key')  # for add condition
ALL_COLUMNS = NamedObject('All Columns')


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
        # 注意，这里实际上读了 self.keys()，所以cache已经生成了，因此直接调用reserve
        self.available_columns = ability.can_with_record(user, A.READ, self, available=info.select if info else None)
        self.reserve(self.available_columns)
        return self.available_columns

    @property
    def cache(self) -> Dict:
        if self._cache is None:
            self._cache = self._to_dict()
        return self._cache

    def get(self, key, default=None):
        return self.cache.get(key, default)

    def to_dict(self):
        return self.cache.copy()

    def keys(self):
        return self.cache.keys()

    def pop(self, key):
        return self.cache.pop(key)

    def reserve(self, keys):
        cache_keys = set(self.keys())
        for k in cache_keys - set(keys):
            del self.cache[k]

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
    NOT_IN = ('notin', 'not in')
    IS = ('is',)
    IS_NOT = ('isnot', 'is not')
    AND = ('and',)
    OR = ('or',)
    CONTAINS = ('contains',)

    ALL = set(EQ + NE + LT + LE + GE + GT + IN + IS + IS_NOT + CONTAINS)


SQL_OP.txt2op = {}
for i in SQL_OP:
    if i == SQL_OP.ALL: continue
    for opval in i.value:
        SQL_OP.txt2op[opval] = i


class QueryConditions(list):
    """ 查询条件，这是 SQLQueryInfo 的一部分。与 list 实际没有太大不同，独立为类型的目的是使其能与list区分开来 """
    def __contains__(self, item):
        for i in self:
            if i[0] == item:
                return True

    def find(self, column):
        ret = []
        for i in self:
            if i[0] == column:
                ret.append(i)
        return ret

    def map(self, key, func):
        for i in self:
            if i[0] == key:
                i[:] = func(i)


class SQLQueryInfo:
    """ SQL查询参数。"""
    def __init__(self, params=None, view=None):
        # self.select: Union[Set[str], object]
        # self.orders: List[SQLQueryOrder]
        # self.loadfk: Dict[str, List[Dict[str, object]]]

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
            else: raise InvalidParams("Invalid order syntax")

            order = order.lower()
            if order not in ('asc', 'desc', 'default'):
                raise InvalidParams('Invalid order mode: %s' % order)

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
            raise InvalidParams('Invalid select')

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
            raise InvalidParams("No column(s) selected")
        return selected_columns

    @classmethod
    def parse_load_fk(cls, data: Dict[str, List[Dict[str, object]]]) -> Dict[str, List[Dict[str, object]]]:
        """
        :param data:{
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
        default_value_dict = {'role': None, 'as': None, 'table': None, 'loadfk': None}

        def value_normalize_dict(value):
            def check(k, v):
                if k == 'role': return isinstance(v, str)
                if k == 'as': return isinstance(v, str)
                if k == 'table': return isinstance(v, str)
                if k == 'loadfk': return isinstance(v, dict)

            valid = {k: v for k, v in value.items() if check(k, v)}
            if not valid: return default_value_dict.copy()
            if 'loadfk' in valid and valid['loadfk']:
                valid['loadfk'] = cls.parse_load_fk(valid['loadfk'])
            for k, v in default_value_dict.items():
                valid.setdefault(k, v)
            return valid

        def value_normalize(value, no_list=True):
            if value is None:
                return default_value_dict.copy()
            elif not no_list and isinstance(value, List):
                # <column>: [value1, value2, ...]
                return list(map(value_normalize, value))
            elif isinstance(value, str):
                # <column>: role
                val = default_value_dict.copy()
                val['role'] = value
                return val
            elif isinstance(value, Dict):
                # {'role': <str>, 'as': <str>, ...}
                return value_normalize_dict(value)
            else:
                raise InvalidParams('Invalid syntax for "loadfk": %s' % value)

        # 对全部项进行检查
        new_data = {}
        if not isinstance(data, dict):
            raise InvalidParams('Invalid syntax for "loadfk": %s' % data)
        for k, v in data.items():
            nv = value_normalize(v, False)
            new_data[k] = nv if isinstance(nv, List) else [nv]
        return new_data

    def add_condition(self, field_name, op, value):
        """
        Add a query condition and validate it.
        raise ParamsException if failed.
        self.view required
        :param field_name:
        :param op:
        :param value:
        :return: None
        """
        if not isinstance(op, SQL_OP):
            if op not in SQL_OP.txt2op:
                raise SQLOperatorInvalid(op)
            else:
                op = SQL_OP.txt2op.get(op)
        self.conditions.append([field_name, op, value])  # 注意，必须是list

    def parse_then_add_condition(self, field_name, op_name, value):
        if op_name not in SQL_OP.txt2op:
            raise SQLOperatorInvalid(op_name)
        op = SQL_OP.txt2op.get(op_name)
        if op in (SQL_OP.IN, SQL_OP.NOT_IN):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                raise InvalidParams('The right value of "in" condition must be serialized json string: %s' % value)
        self.add_condition(field_name, op, value)

    def clear_condition(self):
        self.conditions.clear()

    def parse(self, params):
        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]

            if field_name.startswith('$'):
                continue
            elif field_name == 'order':
                self.orders = self.parse_order(value)
                continue
            elif field_name == 'select':
                self.select = self.parse_select(value)
                continue
            elif field_name == 'loadfk':
                try:
                    value = json.loads(value)  # [List, Dict[str, str]]
                except (json.JSONDecodeError, TypeError):
                    raise InvalidParams('Invalid json syntax for "loadfk": %s' % value)
                self.loadfk = self.parse_load_fk(value)
                continue

            op = info[1] if len(info) > 1 else '='
            self.parse_then_add_condition(field_name, op, value)

    def check_query_permission(self, view: "AbstractSQLView"):
        user = view.current_user if view.can_get_user else None
        return self.check_query_permission_full(user, view.table_name, view.ability, view)

    def check_query_permission_full(self, user: "BaseUser", table: str, ability: "Ability", view: "AbstractSQLView"):
        from .permission import A

        # QUERY 权限检查，通不过则报错
        checking_columns = []
        for field_name, op, value in self.conditions:
            checking_columns.append(field_name)

        if checking_columns and not ability.can_with_columns(user, A.QUERY, table, checking_columns):
            raise PermissionDenied("None of these columns had permission to %s: %r of %r" % (A.QUERY, checking_columns, table))

        # READ 权限检查，通不过时将其过滤
        checking_columns = self.loadfk.keys()  # 外键过滤
        new_loadfk = ability.can_with_columns(user, A.READ, table, checking_columns)
        self.loadfk = dict_filter(self.loadfk, new_loadfk)

        new_select = ability.can_with_columns(user, A.READ, table, self.select)  # select 过滤
        self.set_select(new_select)

        # 设置附加条件
        ability.setup_extra_query_conditions(user, table, self, view)

    def bind(self, view: "AbstractSQLView"):
        def check_column_exists(column):
            if column is PRIMARY_KEY:
                return
            if column not in view.fields:
                raise ColumnNotFound(column)

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

        # where convert
        for i in self.conditions:
            field_name, op, value = i
            check_column_exists(field_name)
            if field_name == PRIMARY_KEY:
                i[0] = field_name = view.primary_key

        # permission check
        # 是否需要一个 order 权限？
        if view.ability:
            self.check_query_permission(view)

        # where check
        for i in self.conditions:
            field_name, op, value = i
            check_column_exists(field_name)
            if field_name == PRIMARY_KEY:
                i[0] = field_name = view.primary_key
            field_type = view.fields[field_name]
            conv = lambda x: None if x in ('null', None) else field_type.value(x)
            try:
                # 注：外键的类型会是其指向的类型，这里不用担心
                if op in (SQL_OP.IN, SQL_OP.NOT_IN):
                    assert isinstance(value, Iterable)
                    i[2] = list(map(conv, value))
                else:
                    i[2] = conv(value)

            except Exception as e:
                raise InvalidParams("Column bad value: %s" % field_name)

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

            for field_name, values_lst in data.items():
                # field_name: [{'role': role, 'loadfk': {...}}]
                # field_name: [{'as': 's24h', 'table': 's24', 'role': role}]

                # 检查列是否存在
                if field_name not in the_view.fields:
                    raise ColumnNotFound(field_name)

                # 检查列是否是合法的外键列
                fks = the_view.foreign_keys.get(field_name, None)
                if not fks: raise ColumnIsNotForeignKey(field_name)

                for values in values_lst:
                    # 检查是否采用别名将外键对应到特定表上
                    if values['table']:
                        if values['table'] not in the_view.foreign_keys_table_alias:
                            raise ResourceException('Foreign key not match the table: %r -> %r' % (field_name, values['table']))
                        fk = the_view.foreign_keys_table_alias[values['table']]
                        values['table'] = fk.rel_table
                    else:
                        fk = fks[0]  # 取第一个结果（即默认外键）
                        values['table'] = fk.rel_table

                    # 检查对应的表是否存在
                    if fk.rel_table not in app.tables:
                        raise TableNotFound("Foreign key refer to a table not exists: %r -> %r" % (field_name, fk.rel_table))

                    # 检查对应的表的角色是否存在
                    if values['role'] not in app.table_permissions[fk.rel_table].roles:
                        raise InvalidRole('%s of %s' % (values['role'], fk.rel_table))

                    # 递归外键读取
                    if values['loadfk']:
                        check_loadfk_data(app.tables[fk.rel_table], values['loadfk'])

        if self.loadfk:
            check_loadfk_data(view, self.loadfk)


class UpdateInfo:
    def __init__(self, key, op, val):
        assert op in ('incr', 'to')
        self.key = key
        self.op = op
        self.val = val

    def __repr__(self):
        return '<%s %s>' % (self.op, self.val)


class SQLValuesToWrite(dict):
    def __init__(self, post_data=None, view=None, action=None, records=None):
        super().__init__()
        self.returning = False
        self._inner_data = {
            'view': view
        }

        if post_data:
            self.parse(post_data)
            if view: self.bind(view, action, records)

    def parse(self, post_data: MultiDict):
        self.clear()
        if isinstance(post_data, dict):
            post_data = MultiDict(post_data)

        for k, v in post_data.items():
            v_all = post_data.getall(k)
            if len(v_all) > 1:
                v = v_all

            if k.startswith('$'):
                continue
            elif k == '_inner_data':
                continue
            elif k == 'returning':
                self.returning = True
                continue
            elif '.' in k:
                k, op = k.rsplit('.', 1)
                v = UpdateInfo(k, op, v)

            self[k] = v

    def check_insert_permission(self, user: "BaseUser", table: str, ability: "Ability"):
        from .permission import A
        columns = self.keys()
        logger.debug('request permission: [%s] of table %r, columns: %s' % (A.CREATE, table, columns))
        is_empty_input = not columns

        # 如果插入数据项为空，那么用户应该至少有一个列的插入权限
        if is_empty_input:
            if self._inner_data.get('view'):
                columns = self._inner_data['view'].fields.keys()

        available = ability.can_with_columns(user, A.CREATE, table, columns)
        if not available: raise PermissionDenied()
        dict_filter_inplace(self, available)

        valid = ability.can_with_columns(user, A.CREATE, table, available)

        if is_empty_input:
            if len(valid) <= 0:
                logger.debug("request permission failed. request / valid: %r, %r" % (list(self.keys()), valid))
                raise PermissionDenied()
        else:
            if len(valid) != len(self):
                logger.debug("request permission failed. request / valid: %r, %r" % (list(self.keys()), valid))
                raise PermissionDenied()

        logger.debug("request permission successed: %r" % list(self.keys()))

    def check_update_permission(self, user: "BaseUser", table: str, ability: "Ability", records):
        from .permission import A
        columns = self.keys()
        logger.debug('request permission: [%s] of table %r, columns: %s' % (A.WRITE, table, columns))
        available = ability.can_with_columns(user, A.WRITE, table, columns)
        if not available: raise PermissionDenied()
        dict_filter_inplace(self, available)

        for record in records:
            valid = ability.can_with_record(user, A.WRITE, record, available=available)
            if len(valid) != len(self):
                logger.debug("request permission failed. request / valid: %r, %r" % (list(self.keys()), valid))
                raise PermissionDenied()

        logger.debug("request permission successed: %r" % list(self.keys()))

    def check_write_permission(self, view: "AbstractSQLView", action, records=None):
        from .permission import A
        user = view.current_user if view.can_get_user else None
        if action == A.WRITE:
            self.check_update_permission(user, view.table_name, view.ability, records)
        elif action == A.CREATE:
            self.check_insert_permission(user, view.table_name, view.ability)
        else:
            raise SlimException("Invalid action to write: %r" % action)

    def value_convert(self, view: "AbstractSQLView"):
        for k, v in self.items():
            field_type = view.fields[k]
            conv = lambda x: None if x in ('null', None) else field_type.value(x)
            try:
                if isinstance(v, UpdateInfo):
                    if v.op == 'to':
                        self[k] = conv(v.val)
                    elif v.op == 'incr':
                        v.val = conv(v.val)
                else:
                    self[k] = conv(v)
            except:
                traceback.print_exc()
                raise InvalidPostData("Column bad value: %s" % k)

    def bind(self, view: "AbstractSQLView", action=None, records=None):
        dict_filter_inplace(self, view.fields.keys())

        if len(self) == 0:
            logger.debug('No values to write after filtered by table fields: %s' % view.table_name)
            # raise InvalidPostData()

        if action:
            self.check_write_permission(view, action, records)

        self.value_convert(view)
