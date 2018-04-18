import json
import logging
from enum import Enum
from typing import Union, Iterable, List
from ..utils import blob_converter, json_converter
from ..exception import SyntaxException, ResourceException, ParamsException, \
    PermissionDeniedException, ColumnNotFound, ColumnIsNotForeignKey

logger = logging.getLogger(__name__)


class SQL_TYPE(Enum):
    INT = int
    FLOAT = float
    STRING = str
    BOOLEAN = bool
    BLOB = blob_converter
    JSON = json_converter


class SQLForeignKey:
    def __init__(self, rel_table: str, rel_field: str, rel_type: SQL_TYPE):
        self.rel_table = rel_table
        self.rel_field = rel_field
        self.rel_type = rel_type


class SQL_OP(Enum):
    EQ = ('eq', '==')
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


class SQLQueryInfo(dict):
    """ 查询参数。目的同 QueryArguments，即与其他 dict 能够区分 """
    PRIMARY_KEY = object() # for add condition

    @property
    def conditions(self) -> QueryConditions:
        return self['conditions']

    @property
    def orders(self):
        return self['orders']

    @property
    def select(self):
        return self['select']

    def __init__(self, view=None, **kwargs):
        self.view = view
        self['select'] = None
        self['conditions'] = []
        self['orders'] = []
        self['loadfk'] = {}
        super().__init__(**kwargs)

    def set_view(self, view):
        """
        :param view: SQLView class or instance
        :return:
        """
        self.view = view

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

            orders.append([column, order])
        return orders

    def _parse_select(self, text: str):
        """
        get columns from select text
        :param text: col1, col2
        :return: None or [col1, col2]
        """
        info = set(map(str.strip, text.split(',')))
        if '*' in info:
            return None
        else:
            selected_columns = []
            for column in info:
                if column:
                    if column not in self.view.fields:
                        raise ColumnNotFound(column)
                    selected_columns.append(column)
            if not selected_columns:
                raise ResourceException("No column(s) selected")
            return selected_columns

    @classmethod
    def add_load_foreign_key(cls, column, data):
        # TODO: 这是什么来着？
        pass

    @staticmethod
    def _parse_load_fk(value: str):
        """
        :param value:
        :return: {
            <column>: role,
            <column2>: role,
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

        # 这里不检查列是否存在了。
        # 因为在递归读取中，会涉及别的表。
        def check_and_rebuild(column, data):
            # data: str, role name
            # dict, {'role': <str>, 'as': <str>}
            if isinstance(data, str):
                data = {'role': data}
            elif isinstance(data, dict):
                data = {'role': data.get('role', None)}

            # 递归外键读取
            if ('loadfk' in data) and (data['loadfk'] is not None):
                data['loadfk'] = translate(data['loadfk'])
            return data

        def translate(value):
            for column, items in value.items():
                ret = []
                if not isinstance(items, Iterable):
                    items = [items]

                for i in items:
                    ret.append(check_and_rebuild(column, i))

                value[column] = ret
            return value

        return translate(value)

    def set_select(self, field_names):
        if field_names is None:
            self['select'] = self.view.fields.keys()
        else:
            self['select'] = field_names

    def add_select(self, column):
        assert column in self.view.fields
        if not self['select']:
            self['select'] = [column]
        else:
            if column not in self['select']:
                self['select'].append(column)

    def remove_select(self, column):
        if not self['select']:
            return
        if column in self['select']:
            self['select'].remove(column)
            return True

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
        if field_name == self.PRIMARY_KEY:
            field_name = self.view.primary_key

        if field_name not in self.view.fields:
            raise ParamsException('Column not found: %s' % field_name)

        if op not in SQL_OP:
            raise ParamsException('Invalid operator: %s' % op)

        op = valid_sql_operator[op]

        # is 和 is not 可以确保完成了初步值转换
        if op in ('is', 'isnot'):
            if value not in ('null', None):
                raise ParamsException('Invalid value: %s (must be null)' % value)
            elif op in ('isnot', 'is not'):
                op = 'is not'
            value = None

        if op == 'in':
            if type(value) == str:
                try:
                    value = json.loads(value)
                except json.decoder.JSONDecodeError:
                    raise ParamsException('Invalid value: %s (must be json)' % value)
            assert isinstance(value, Iterable)

        self.conditions.append((field_name, op, value))

    def clear_condition(self):
        self.conditions.clear()

    @classmethod
    def new(cls, view) -> 'SQLQueryInfo':
        """ parse params to query information """
        conditions = QueryConditions()
        return SQLQueryInfo(
            view=view,
            select=None,
            conditions=conditions,
            orders=[]
        )

    def init(self, params):
        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]
            if field_name == 'order':
                self['orders'] = self._parse_order(value)
                continue
            elif field_name == 'select':
                self['select'] = self._parse_select(value)
                continue
            elif field_name == 'loadfk':
                self['loadfk'] = self._parse_load_fk(value)
                continue

            op = info[1] if len(info) > 1 else '='
            self.add_condition(field_name, op, value)

    def check_permission(self, ability):
        from .permission import A
        view = self.view
        # 查询权限检查
        checking_columns = []
        for field_name, op, value in self.conditions:
            checking_columns.append(field_name)

        if checking_columns and not ability.can_with_columns(view.current_user, A.QUERY, view.table_name, checking_columns):
            raise PermissionDeniedException("None of these columns had permission to %r: %r" % (A.QUERY, checking_columns))

        # 读取权限检查，限定被查询的列
        if self['select'] is None:
            self['select'] = self.view.fields.keys()
        self['select'] = ability.can_with_columns(view.current_user, A.READ, view.table_name, self['select'])


class SQLValuesToWrite(dict):
    pass
