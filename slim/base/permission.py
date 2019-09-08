import copy
import logging
from typing import Dict, Tuple, Any, TYPE_CHECKING, Optional

from .sqlfuncs import DataRecord
from .user import BaseUser

if TYPE_CHECKING:
    from .sqlquery import SQLQueryInfo
    from slim.base.view import AbstractSQLView

logger = logging.getLogger(__name__)


class A:
    QUERY = 'query'
    READ = 'read'
    WRITE = 'write'
    CREATE = 'create'
    DELETE = 'delete'

    ALL = QUERY, READ, WRITE, CREATE, DELETE


class AbilityTable:
    def __init__(self, name):
        self.table = name

    def __eq__(self, other):
        return self.table == other.table

    def __repr__(self):
        return '<Table %r>' % self.table


class AbilityColumn:
    def __init__(self, table, column):
        self.table = table
        self.column = column

    def __eq__(self, other):
        return self.table == other.table and self.column == other.column

    def __ne__(self, other):
        return self.table != other.table or self.column != other.column

    def __repr__(self):
        return '<Column %r.%r>' % (self.table, self.column)


class Ability:
    def __init__(self, data: dict = None, *, based_on=None):
        """
        {
            'user': {
                'username': ['query', 'read'],
                'nickname': ['query', 'read'],
                'password': ['query', 'read'],
                '*': ['write'],
            },
            'topic': '*',
            'test': ['query', 'read', 'write', 'create', 'delete'],
        }
        :param data:
        :param based_on: 
        """
        self.role = None
        if based_on:
            self.rules = copy.deepcopy(based_on.rules)
        else:
            self.rules = {}

        self.query_condition_params = {}
        self.query_condition_params_funcs = {}
        self.common_checks = []
        self.record_checks = []

        if data:
            # 权限继承对应到列
            def convert(val: str):
                if val == '*': return '*'
                val = val.upper()
                ret = []
                if 'Q' in val: ret.append(A.QUERY)
                if 'W' in val: ret.append(A.WRITE)
                if 'R' in val: ret.append(A.READ)
                if 'C' in val: ret.append(A.CREATE)
                if 'D' in val: ret.append(A.DELETE)
                return ret

            def parse(v):
                ret = copy.deepcopy(v)
                if ret == str:
                    ret = convert(ret)
                elif ret == dict:
                    for k, v in ret.items():
                        ret[k] = convert(v)
                return ret

            for k, v in data.items():
                if isinstance(v, dict):
                    if k in self.rules and isinstance(self.rules[k], dict):
                        self.rules[k].update(parse(v))
                        continue
                self.rules[k] = parse(v)

    def add_query_condition(self, table, params=None, *, func=None):
        if params:
            self.query_condition_params.setdefault(table, [])
            self.query_condition_params[table].append(params)

        if func:
            self.query_condition_params_funcs.setdefault(table, [])
            self.query_condition_params_funcs[table].append(func)

            """def func(ability: Ability, user, query: 'SQLQueryInfo', view: "AbstractSQLView"):
                 pass
            """

    def setup_extra_query_conditions(self, user, table, query: 'SQLQueryInfo', view: "AbstractSQLView"):
        if table in self.query_condition_params:
            # TODO: Check once
            for items in self.query_condition_params[table]:
                for i in items:
                    query.add_condition(*i)

        if table in self.query_condition_params_funcs:
            for func in self.query_condition_params_funcs[table]:
                if func.__code__.co_argcount == 3:
                    func(self, user, query)
                else:
                    func(self, user, query, view)

    def add_common_check(self, actions, table, func):
        """
        emitted before query
        :param actions:
        :param table:
        :param func:
        :return:
        """
        self.common_checks.append([table, actions, func])

        """def func(ability, user, action, available_columns: list):
            pass
        """

    def add_record_check(self, actions, table, func):
        # emitted after query
        # table: 'table_name'
        # column: ('table_name', 'column_name')
        assert isinstance(table, str), '`table` must be table name'
        for i in actions:
            assert i not in (A.QUERY, A.CREATE), "meaningless action check with record: [%s]" % i

        self.record_checks.append([table, actions, func])

        """def func(ability, user, action, record: DataRecord, available_columns: list):
            pass
        """

    def _parse_permission(self, obj):
        """
        从 obj 中取出权限
        :param obj:
        :return: [A.QUERY, A.WRITE, ...]
        """
        if isinstance(obj, str):
            if obj == '*':
                return A.ALL
            elif obj in A.ALL:
                return obj,
            else:
                logger.warning('Invalid permission action: %s', obj)
        elif isinstance(obj, (list, tuple)):
            for i in obj:
                if i not in A.ALL:
                    logger.warning('Invalid permission action: %s', i)
            return obj
        elif isinstance(obj, dict):
            return self._parse_permission(obj.get('*'))

    def can_with_columns(self, user, action, table, columns):
        """
        根据权限进行列过滤
        注意一点，只要有一个条件能够通过权限检测，那么过滤后还会有剩余条件，最终就不会报错。
        如果全部条件都不能过检测，就会爆出权限错误了。

        :param user:
        :param action: 行为
        :param table: 表名
        :param columns: 列名列表
        :return: 可用列的列表
        """
        # TODO: 此过程可以加缓存
        # 全局

        global_data = self.rules.get('*')
        global_actions = self._parse_permission(global_data)
        if global_actions and action in global_actions:
            available = list(columns)
        else:
            available = []

        # table
        table_data = self.rules.get(table)
        table_actions = self._parse_permission(table_data)

        if table_actions and action in table_actions:
            available = list(columns)

        # column
        if type(table_data) == dict:
            # 这意味着有详细的列权限设定，不然类型是 list
            for column in columns:
                column_actions = self._parse_permission(table_data.get(column))
                if column_actions is not None:
                    if action in column_actions:
                        # 有权限，试图加入列表
                        if column not in available:
                            available.append(column)
                    else:
                        # 无权限，从列表剔除
                        if column in available:
                            available.remove(column)

        for check in self.common_checks:
            if check[0] == table and action in check[1]:
                ret = check[-1](self, user, action, available)
                if isinstance(ret, (tuple, set, list)):
                    # 返回列表则进行值覆盖
                    available = list(ret)
                elif ret == '*':
                    # 返回 * 加上所有可用列
                    available = list(columns)
                elif ret is False:
                    # 返回 false 清空
                    available = []
                if not available: break

        return available

    def can_with_record(self, user, action, record: DataRecord, *, available=None):
        """
        进行基于 Record 的权限判定，返回可用列。
        :param user:
        :param action:
        :param record:
        :param available: 限定检查范围
        :return: 可用列
        """
        assert action not in (A.QUERY, A.CREATE), "meaningless action check with record: [%s]" % action

        # 先行匹配规则适用范围
        rules = []
        for rule in self.record_checks:
            if record.table == rule[0] and action in rule[1]:
                rules.append(rule)

        # 逐个过检查
        if available is None: available = self.can_with_columns(user, action, record.table, record.keys())
        else: available = list(available)
        bak = available.copy()

        for rule in rules:
            ret = rule[-1](self, user, action, record, available)
            if isinstance(ret, (tuple, set, list)):
                available = list(ret)
            elif ret == '*':
                available = list(bak)
            elif not ret:
                available = []

        return available


class Permissions:
    def __init__(self, app):
        self.app = app
        self.role_to_ability = {}

    @property
    def roles(self):
        return self.role_to_ability

    def add(self, role: Optional[str], ability: Ability):
        assert isinstance(ability, Ability)
        ability.role = role
        self.role_to_ability[role] = ability

    def request_role(self, user: Optional[BaseUser], role) -> Optional[Ability]:
        # '' 视为 None 的等价角色
        if role is '':
            role = None

        if user is None:
            # 当用户不存在，那么角色仅有可能为None
            if role is None:
                return self.role_to_ability.get(None)
        else:
            if role in user.roles:
                return self.role_to_ability.get(role)


ALL_PERMISSION = object()
EMPTY_PERMISSION = object()

NO_PERMISSION = EMPTY_PERMISSION
