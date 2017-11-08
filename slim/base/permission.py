import copy
import logging
from typing import Dict, Tuple, Any

logger = logging.getLogger(__name__)


class BaseUser:
    def __init__(self):
        self.roles = [None]


class A:
    QUERY = 'query'
    READ = 'read'
    WRITE = 'write'
    CREATE = 'create'
    DELETE = 'delete'

    ALL = 'query', 'read', 'write', 'create', 'delete'


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


class AbilityRecord:
    def __init__(self, table_name, val):
        self.table = table_name
        self.val = val

    def get(self, key):
        raise NotImplementedError()

    def keys(self):
        raise NotImplementedError()

    def has(self, key):
        raise NotImplementedError()

    def to_dict(self, available_columns=None) -> Dict:
        raise NotImplementedError()


class Ability:
    def __init__(self, role: (str, int), data: dict = None, based_on=None):
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
        :param role: 
        :param data: 
        :param based_on: 
        """
        self.role = role
        if based_on:
            self.rules = copy.deepcopy(based_on.rules)
            self.record_rules = copy.deepcopy(based_on.record_rules)
        else:
            self.rules = {}
            self.record_rules = []

        if data:
            # 权限继承对应到列
            for k, v in data.items():
                if isinstance(v, dict):
                    if k in self.rules and isinstance(self.rules[k], dict):
                        self.rules[k].update(copy.deepcopy(v))
                        continue
                self.rules[k] = copy.deepcopy(v)

    def add_record_rule(self, wanted_actions, subject_cls: (AbilityTable, AbilityColumn), *, func):
        # subject_cls value:
        # table: 'table_name'
        # column: ('table_name', 'column_name')
        self.record_rules.append([subject_cls, wanted_actions, func])

        """def func(ability, user, cur_action, record: AbilityRecord) -> bool:
            pass
        """

    @staticmethod
    def _is_rule_match_record(record_rule, action, record: AbilityRecord) -> Tuple[Any, bool]:
        """
        检查记录(从数据库查询出的数据的单项)是否匹配对应规则，在查询之后执行
        :param record_rule:
        :param action:
        :param record:
        :return:
        """
        if action in record_rule[1]:
            obj = record_rule[0]
            if isinstance(obj, AbilityTable):
                return 'table', obj.table == record.table
            elif isinstance(obj, AbilityColumn):
                return 'column', obj.table == record.table and record.has(obj.column)
        return None, False

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

    def can(self, user, action, *subjects):
        """
        can with tables or columns before query
        :param user:
        :param action:
        :param subjects: [('table_name', 'column_name')] or 'table_name'
        :return:
        """
        ret_lst = []
        global_data = self.rules.get('*')
        global_actions = self._parse_permission(global_data)

        for i in subjects:
            ret = False

            if isinstance(i, (tuple, list)):
                table, column = i
            else:
                table, column = i, None

            if global_actions and action in global_actions:
                ret = True

            table_data = self.rules.get(table)
            table_actions = self._parse_permission(table_data)

            # table
            if table_actions and action in table_actions:
                ret = True

            # column
            if type(table_data) == dict:
                column_actions = self._parse_permission(table_data.get(column))
                if column_actions is not None:
                    ret = action in column_actions

            ret_lst.append(ret)

        return ret_lst

    def cannot(self, user, action, *subjects):
        """
        cannot with tables or columns before query
        :param user:
        :param action:
        :param subjects:
        :return:
        """
        func = lambda x: not x
        return list(map(func, self.can(user, action, *subjects)))

    def filter_columns(self, table, columns, action):
        """
        根据权限进行列过滤
        :param table: 表名
        :param columns: 列名列表
        :param action: 行为
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
        for column in columns:
            if type(table_data) == dict:
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

        return available

    def filter_record(self, user, action, record: AbilityRecord, *, available=None):
        """
        filter record columns by rules and action
        在查询完成之后，根据规则对记录进行过滤
        特别解释一下，因为不同orm的Record并不相同，这里只返回可用的数据列的列表
        自行实现对列的过滤。如果返回值为空表示完全无权或输入数据为空
        :param user: 
        :param action: 
        :param record:
        :param available:
        :return: 可用列
        """
        if available is None:
            # available = record.keys()
            # 为了避免不必要的麻烦（主要是没有 info['select'] 又需要读出 record 的情况，例如 insert 和 update）
            # 这里直接再对列做一次过滤
            available = self.filter_columns(record.table, record.keys(), action)

        # 先行匹配规则适用范围
        rules = {'table': [], 'column': []}
        for rule in self.record_rules:
            obj_type, exists = self._is_rule_match_record(rule, action, record)
            if exists:
                rules[obj_type].append(rule)

        # 若满足条件，逐条检测覆盖表权限
        for rule in rules['table']:
            func = rule[-1]
            ret = func(self, user, action, record)
            if ret is True:
                available = list(record.keys())
            elif ret is False:
                available = []

        # 逐条添加列权限
        for rule in rules['column']:
            func = rule[-1]
            column = rule[0].column
            ret = func(self, user, action, record)
            if ret is True:
                if column not in available:
                    available.append(column)
            elif ret is False:
                if column in available:
                    available.remove(column)

        return available


class Permissions:
    def __init__(self):
        self.role_to_ability = {}

    def add(self, ability: Ability):
        self.role_to_ability[ability.role] = ability

    def request_role(self, user: BaseUser, role) -> Ability:
        if user is None:
            return self.role_to_ability.get(role)
        if role in user.roles:
            return self.role_to_ability.get(role)

    def copy(self) -> 'Permissions':
        instance = Permissions()
        # TODO: 这里理论上存在 BUG，子类继承权限后如果进行修改，那么父类的 ability 也会跟着变化
        instance.role_to_ability = self.role_to_ability.copy()
        return instance
