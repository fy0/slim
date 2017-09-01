import logging
from typing import Dict

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
            self.data = based_on.data.copy()
            # rules
        else:
            self.data = {}
        if data: self.data.update(data)
        self.rules = []
        self.record_rules = []

    def add_rule(self, actions, table, *extra_conditions, func=None):
        self.rules.append([table, actions, extra_conditions, func])

    def get_additional_args(self, user, action, table):
        additional_args = []
        for rtable, ractions, extra_conditions, func in self.rules:
            if table == rtable and action in ractions:
                if func:
                    additional_args.extend(func(self, user, action, table))
                additional_args.extend(extra_conditions)
        return additional_args

    def add_record_rule(self, actions, subject_cls: (AbilityTable, AbilityColumn), *, func=None):
        # subject_cls value:
        # table: 'table_name'
        # column: ('table_name', 'column_name')
        self.record_rules.append([subject_cls, actions, func])

        """def func(ability, user, action, record: AbilityRecord):
            pass
        """

    def _get_direct_permission(self, obj):
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
            return self._get_direct_permission(obj.get('*'))

    def can(self, user, action, *subjects):
        ret_lst = []
        global_data = self.data.get('*')
        global_actions = self._get_direct_permission(global_data)

        for i in subjects:
            ret = False

            if isinstance(i, (tuple, list)):
                table, column = i
            else:
                table, column = i, None

            if global_actions and action in global_actions:
                ret = True

            table_data = self.data.get(table)
            table_actions = self._get_direct_permission(table_data)

            # table
            if table_actions and action in table_actions:
                ret = True

            # column
            if type(table_data) == dict:
                column_actions = self._get_direct_permission(table_data.get(column))
                if column_actions is not None:
                    ret = action in column_actions

            ret_lst.append(ret)

        return ret_lst

    def can_query(self, user, *subjects):
        """
        这一查询不能附加 condition
        :param user: 
        :param subjects: 
        :return: 
        """
        return self.can(user, A.QUERY, *subjects)

    def cannot(self, user, action, *subjects):
        func = lambda x: not x
        return list(map(func, self.can(user, action, *subjects)))

    def filter_columns_by_action(self, table, columns, action):
        # 全局
        global_data = self.data.get('*')
        global_actions = self._get_direct_permission(global_data)
        if global_actions and action in global_actions:
            available = list(columns)
        else:
            available = []

        # table
        table_data = self.data.get(table)
        table_actions = self._get_direct_permission(table_data)

        if table_actions and action in table_actions:
            available = list(columns)

        # column
        for column in columns:
            if type(table_data) == dict:
                column_actions = self._get_direct_permission(table_data.get(column))
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

    @staticmethod
    def is_rule_match_record(rule, action, record: AbilityRecord):
        if action in rule[1]:
            obj = rule[0]
            if isinstance(obj, AbilityTable):
                return 'table', obj.table == record.table
            elif isinstance(obj, AbilityColumn):
                return 'column', obj.table == record.table and record.has(obj.column)
        return None, False

    def filter_record_columns_by_action(self, user, action, record: AbilityRecord):
        """
        特别解释一下，因为不同orm的Record并不相同，这里只返回可用的数据列
        自行实现对列的过滤。如果返回值为空表示完全无权
        
        :param user: 
        :param action: 
        :param record: 
        :return: 
        """
        available = self.filter_columns_by_action(record.table, record.keys(), action)

        rules = {'table': [], 'column': []}
        for rule in self.record_rules:
            obj_type, exists = self.is_rule_match_record(rule, action, record)
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
        instance.key_to_roles = self.role_to_ability.copy()
        return instance
