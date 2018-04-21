import json
import logging
from enum import Enum
from typing import Union, Iterable, List, TYPE_CHECKING, Dict

from ..utils import blob_converter, json_converter, MetaClassForInit, is_py36
from ..exception import SyntaxException, ResourceException, ParamsException, \
    PermissionDeniedException, ColumnNotFound, ColumnIsNotForeignKey, SQLOperatorInvalid, RoleNotFound, SlimException

if TYPE_CHECKING:
    from .view import AbstractSQLView


logger = logging.getLogger(__name__)


class SQL_TYPE(Enum):
    INT = int
    FLOAT = float
    STRING = str
    BOOLEAN = bool
    BLOB = blob_converter
    JSON = json_converter


class SQLForeignKey:
    def __init__(self, rel_table: str, rel_field: str, rel_type: SQL_TYPE, is_soft_key=False):
        self.rel_table = rel_table
        self.rel_field = rel_field
        self.rel_type = rel_type
        self.is_soft_key = is_soft_key


class SQLQueryOrder:
    def __init__(self, column, order):
        self.column = column
        self.order = order


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
    """ 查询参数。目的同 QueryArguments，即与其他 dict 能够区分 """
    PRIMARY_KEY = object() # for add condition

    def __init__(self):
        if is_py36:
            self.select: List[str]
            self.orders: List[SQLQueryOrder]
            self.loadfk: Dict[str, List[Dict[str, object]]]

        self.select = None
        self.conditions = QueryConditions()
        self.orders = []
        self.loadfk = None

    @staticmethod
    def _parse_order(text):
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

    @staticmethod
    def _parse_select(text: str):
        """
        get columns from select text
        :param text: col1, col2
        :return: None or [col1, col2]
        """
        if text == '*':
            return None  # None means ALL
        info = set(map(str.strip, text.split(',')))
        selected_columns = list(filter(lambda x: x, info))
        if not selected_columns:
            raise ResourceException("No column(s) selected")
        return selected_columns

    @staticmethod
    def _parse_load_fk(value: str) -> Dict[str, List[Dict[str, object]]]:
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
            if data['loadfk'] is not None:
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
        self.conditions.append((field_name, op, value))

    def clear_condition(self):
        self.conditions.clear()

    @classmethod
    def new(cls, params=None, view=None) -> 'SQLQueryInfo':
        query = SQLQueryInfo()
        if params: query.parse(params)
        if view: query.bind(view)
        return query

    def parse(self, params):
        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]
            if field_name == 'order':
                self.orders = self._parse_order(value)
                continue
            elif field_name == 'select':
                self.select = self._parse_select(value)
                continue
            elif field_name == 'loadfk':
                self.loadfk = self._parse_load_fk(value)
                continue

            op = info[1] if len(info) > 1 else '='
            self.add_condition(field_name, op, value)

    def bind(self, view: "AbstractSQLView"):
        def check_column_exists(column):
            if column is self.PRIMARY_KEY:
                return
            if field_name not in view.fields:
                raise ColumnNotFound(field_name)

        # select check
        if self.select is None:
            self.select = view.fields.keys()
        else:
            for i, field_name in enumerate(self.select):
                check_column_exists(field_name)
                if field_name == self.PRIMARY_KEY:
                    if not isinstance(self.select, List):
                        self.select = list(self.select)
                    self.select[i] = view.primary_key

        # where check
        for i in self.conditions:
            field_name, op, value = i
            check_column_exists(field_name)
            if field_name == self.PRIMARY_KEY:
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
            if od.column == self.PRIMARY_KEY:
                self.orders[i] = view.primary_key

        # foreign key check
        app = view.app

        def check_loadfk_data(the_view, data):
            if self.PRIMARY_KEY in data:
                data[the_view.primary_key] = data[self.PRIMARY_KEY]
                del data[self.PRIMARY_KEY]

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


class SQLValuesToWrite(dict):
    pass
