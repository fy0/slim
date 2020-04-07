import copy
import logging
from typing import Dict, Tuple, Any, TYPE_CHECKING, Optional, List, Set, Iterable, Union, Sequence

from schematics import Model
from schematics.types import DictType

from .sqlquery import SQLQueryInfo, SQL_OP
from .sqlfuncs import DataRecord
from .user import BaseUser

if TYPE_CHECKING:
    from .sqlquery import SQLQueryInfo, SQL_OP
    from slim.base.view import AbstractSQLView

logger = logging.getLogger(__name__)


class A:
    QUERY = 'query'
    QUERY_EX = 'query_ex'
    READ = 'read'
    WRITE = 'write'
    CREATE = 'create'
    DELETE = 'delete'

    ALL = {QUERY, READ, WRITE, CREATE, DELETE}
    ALL_EXTRA = {QUERY, QUERY_EX, READ, WRITE, CREATE, DELETE}


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
                '|': ['create'],
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
        assert isinstance(data, dict), "Ability's data Must be dict"

        if data:
            for k, v in data.items():
                if k == '*' or k == '|':
                    # 如果出现默认权限或叠加权限，value应为合法的权限序列
                    self.rules[k] = self._parse_permission_value(v)
                    assert self.rules[k] is not None, f"Invalid actions: {k}, {v}"
                    continue

                elif isinstance(v, (str, list, tuple, set)):
                    # 如果value为序列或字符串，那么格式化为规范形式
                    # 即 {'a': '*'} 规范为 {'a': {'*': A.ALL}}
                    # 或 {'a': A.ALL} 规范为 {'a': {'*': A.ALL}}
                    self.rules[k] = {'*': self._parse_permission_value(v)}

                elif isinstance(v, dict):
                    # 如果Value为dict，那么以update的形式覆盖
                    if k in self.rules:
                        self.rules[k].update(self._parse_permission_value(v))
                    else:
                        self.rules[k] = self._parse_permission_value(v)

    def _parse_permission_value(self, val) -> Set[str]:
        """
        从 obj 中取出权限列表
        :param val:
        :return: {A.QUERY, A.WRITE, ...}
        """
        if isinstance(val, str):
            if val == '*':
                return A.ALL
            val = val.upper()
            ret = set()
            if 'Q' in val: ret.add(A.QUERY)
            if 'QE' in val: ret.add(A.QUERY_EX)
            if 'W' in val: ret.add(A.WRITE)
            if 'R' in val: ret.add(A.READ)
            if 'C' in val: ret.add(A.CREATE)
            if 'D' in val: ret.add(A.DELETE)
            return ret
        elif isinstance(val, (list, tuple, set)):
            ret = set()
            for i in val:
                if i not in A.ALL_EXTRA:
                    logger.warning('Invalid permission action: %s', i)
                else:
                    ret.add(i)
            return ret
        elif isinstance(val, dict):
            ret = {}
            for k, v in val.items():
                ret[k] = self._parse_permission_value(v)
            return ret

    def add_query_condition(self, table, params: Union[Sequence[Sequence], Tuple, List] = None, *, func=None):
        if params:
            self.query_condition_params.setdefault(table, [])
            assert isinstance(params, (List, Tuple)), 'query condition params must be List or Tuple'

            if params:
                if isinstance(params[0], (List, Tuple)):
                    # 第一种情况：[['a', '=', 'b']]
                    for i in params:
                        cond = SQLQueryInfo.check_condition_and_format(i)
                        self.query_condition_params[table].append(cond)
                else:
                    # 第二种情况：['a', '=', 'b']
                    cond = SQLQueryInfo.check_condition_and_format(params)
                    self.query_condition_params[table].append(cond)

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
                query.add_condition(*items)

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

        """def func(ability, user, action, available_columns: Set):
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

    def can_with_columns(self, user, action, table, columns: Iterable) -> Set:
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
        actions_allowed_now: set
        actions_append = set()

        # 取出全局默认权限
        actions_allowed_now = self.rules.get('*', None) or set()
        # 取出全局叠加权限
        for i in self.rules.get('|', []):
            actions_append.add(i)

        # 取出表权限，如果表权限存在，那么会覆盖全局默认权限
        table_data = self.rules.get(table, {})
        actions_allowed_now = table_data.get('*', None) or actions_allowed_now
        # 取出表叠加权限
        for i in table_data.get('|', []):
            actions_append.add(i)

        # 计算列权限
        available = set()

        for column in columns:
            # 列权限 = (配置中的列权限 or 默认权限) | 叠加权限
            column_actions = table_data.get(column, actions_allowed_now) | actions_append

            # 将有权限的列加入可用列表
            if action in column_actions:
                available.add(column)

        # 回调处理
        for check in self.common_checks:
            if check[0] == table and action in check[1]:
                ret = check[-1](self, user, action, available)
                if isinstance(ret, (tuple, set, list)):
                    # 返回列表则进行值覆盖
                    available = set(ret)
                elif ret == '*':
                    # 返回 * 加上所有可用列
                    available = set(columns)
                elif ret is False:
                    # 返回 false 清空
                    available = set()
                if not available: break

        return available

    def can_with_record(self, user, action, record: DataRecord, *, available=None) -> set:
        """
        进行基于 Record 的权限判定，返回可用列。
        :param user:
        :param action:
        :param record:
        :param available: 限定过权限检查的列，为None时，代表全部列（自动填充）
        :return: 可用列
        """
        # TODO: this assert not work, why?
        # assert (action not in {A.QUERY, A.QUERY_EX, A.CREATE}), "meaningless action check with record: [%s]" % action

        # 先行匹配规则适用范围
        rules = []
        for rule in self.record_checks:
            # rule: [table, actions, func]
            if record.table == rule[0] and action in rule[1]:
                rules.append(rule)

        # 逐个过检查
        if available is None:
            # 使用表的所有可用列进行权限测试，留下可以通过的列
            available = set(record.keys())
        else:
            available = set(available)

        available = self.can_with_columns(user, action, record.table, available)

        for rule in rules:
            # rule: [table, actions, func]
            ret = rule[-1](self, user, action, record, available)
            if isinstance(ret, (tuple, set, list)):
                # 返回列表，那么使用改列表
                available = set(ret)
            elif not ret:
                # 没有返回值，清空
                available = set()

        return available


class Permissions:
    def __init__(self, app):
        self.app = app
        self.roles: Dict[Optional[str]: Ability] = {}

    def add(self, role: Optional[str], ability: Ability):
        if role is not None:
            assert isinstance(role, str), 'role name must be Optional[str]'
            assert not ("'" in role and '"' in role), 'invalid role name: %r' % role
        assert isinstance(ability, Ability), 'ability is ' + str(type(ability))
        ability.role = role
        self.roles[role] = ability

    def request_role(self, user: Optional[BaseUser], role) -> Optional[Ability]:
        # '' 视为 None 的等价角色
        if role == '':
            role = None

        if user is None:
            # 当用户不存在，那么角色仅有可能为None
            if role is None:
                return self.roles.get(None)
        else:
            if role in user.roles:
                return self.roles.get(role)


ALL_PERMISSION = object()
EMPTY_PERMISSION = object()
