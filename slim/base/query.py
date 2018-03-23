import json
import logging
from typing import Union, Iterable

from .permission import A
from ..utils import valid_sql_operator
from ..exception import SyntaxException, ResourceException, ParamsException, \
    PermissionDeniedException

logger = logging.getLogger(__name__)


class QueryConditions(list):
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
    PRIMARY_KEY = object() # for add condition

    """ 目的同 QueryArguments，即与其他 dict 能够区分 """
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
        self['format'] = 'dict'
        self['loadfk'] = {}
        super().__init__(**kwargs)

    def set_view(self, view):
        """
        :param view: SQLView class or instance
        :return:
        """
        self.view = view

    def _parse_order(self, text):
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
            if column not in self.view.fields:
                raise ResourceException('Column not found: %s' % column)
            if order not in ('asc', 'desc', 'default'):
                raise SyntaxException('Invalid order name: %s' % order)

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
                        raise ResourceException('Column not found: %s' % column)
                    selected_columns.append(column)
            if not selected_columns:
                raise ResourceException("No column(s) selected")
            return selected_columns

    @classmethod
    def add_load_foreign_key(cls, column, data):
        # TODO: 这是什么来着？
        pass

    def _parse_load_fk(self, value: str):
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
            raise SyntaxException("Invalid json syntax for loadfk: %s" % value)

        if isinstance(value, list):
            new_value = {}
            for i in value:
                new_value[i] = None
            value = new_value

        app = self.view.app
        if isinstance(value, dict):
            roles = self.view.current_user_roles

            def check_valid(view, value):
                for column, data in value.items():
                    if isinstance(data, list):
                        ret = []
                        for i in data:
                            ret.append(solve_data(view, column, i))
                    else:
                        ret = [solve_data(view, column, data)]

                    # 值覆盖
                    value[column] = ret

            def solve_data(view, column, data):
                # data: str, role name
                # dict, {'role': <str>, 'as': <str>}
                if isinstance(data, str):
                    data = {'role': data}
                elif isinstance(data, dict):
                    if 'role' not in data:
                        data['role'] = None
                else:
                    data = {'role': data}

                # 当前用户可用此角色？
                if data['role'] not in roles:
                    raise ResourceException('Role not found: %s' % column)
                # 检查列是否存在
                if column not in view.fields:
                    raise ResourceException('Column not found: %s' % column)
                # 获取对应表名
                table = view.foreign_keys.get(column, None)
                if table is None:
                    raise ResourceException('Not a foreign key field: %s' % column)
                if ('table' in data) and (data['table'] is not None):
                    if data['table'] not in view.foreign_keys_table_alias:
                        raise ResourceException('Foreign key not match the table: %s -> %s' % (column, data['table']))
                    table = view.foreign_keys_table_alias[data['table']]
                else:
                    table = table[0]  # 取第一个结果（即默认外键）
                data['table'] = table
                # 检查表是否存在
                if table not in app.tables:
                    raise ResourceException('Table not found or not a SQLView: %s' % table)
                # 检查对应的表的角色是否存在
                if data['role'] not in app.permissions[table].roles:
                    raise ResourceException('Role not found: %s' % column)

                # 递归外键读取
                if ('loadfk' in data) and (data['loadfk'] is not None):
                    check_valid(app.tables[table], data['loadfk'])
                return data

            check_valid(self.view, value)
            return value
        else:
            raise SyntaxException('Invalid value for "loadfk": %s' % value)

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

        if op not in valid_sql_operator:
            raise ParamsException('Invalid operator: %s' % op)

        op = valid_sql_operator[op]

        # is 和 is not 可以确保完成了初步值转换
        if op in ('is', 'isnot'):
            if value.lower() != 'null':
                raise ParamsException('Invalid value: %s (must be null)' % value)
            if op == 'isnot':
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
    def new(cls, view, params, ability) -> Union['ParamsQueryInfo', None]:
        """ parse params to query information """
        conditions = QueryConditions()
        query = ParamsQueryInfo(
            view=view,
            select=None,
            conditions=conditions,
            orders=[],
            format='dict'
        )

        for key, value in params.items():
            # xxx.{op}
            info = key.split('.', 1)

            field_name = info[0]
            if field_name == 'order':
                query['orders'] = query._parse_order(value)
                continue
            elif field_name == 'select':
                query['select'] = query._parse_select(value)
                continue
            elif field_name == 'loadfk':
                if value:
                    query['loadfk'] = query._parse_load_fk(value)
                continue
            elif field_name == 'data_format':
                query['format'] = value
                continue

            op = info[1] if len(info) > 1 else '='
            query.add_condition(field_name, op, value)

        query.check_permission(ability)
        # 额外附加的参数跳过权限检查
        ability.setup_extra_query_conditions(view.current_user, view.table_name, query)
        logger.debug('query info: %s' % query)

        return query

    def check_permission(self, ability):
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
