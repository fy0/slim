import logging

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

    def add(self, actions, subject_cls: (str, tuple, list), *, func=None, **conditions):
        # subject_cls value:
        # table: 'table_name'
        # column: ('table_name', 'column_name')
        pass

    def _can(self, user, action, *subjects, check_conditions=True):
        def get_direct_permission(obj):
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
                return get_direct_permission(obj.get('*'))

        ret_lst = []
        for i in subjects:
            ret = False

            if isinstance(i, (tuple, list)):
                table, column = i
            else:
                table, column = i, None

            table_data = self.data.get(table)
            table_actions = get_direct_permission(table_data)

            # table
            if table_actions and action in table_actions:
                ret = True

            # column
            if type(table_data) == dict:
                column_actions = get_direct_permission(table_data.get(column))
                if column_actions is not None:
                    ret = action in column_actions

            if check_conditions:
                # rules
                pass

            ret_lst.append(ret)

        return ret_lst

    def can_query(self, user, *subjects):
        """
        这一查询不能附加 condition
        :param user: 
        :param subjects: 
        :return: 
        """
        return self._can(user, A.QUERY, *subjects, check_conditions=False)

    def can(self, user, action, *subjects):
        return self._can(user, action, *subjects, check_conditions=True)

    def cannot(self, user, action, *subjects):
        func = lambda x: not x
        return list(map(func, self._can(user, action, *subjects, check_conditions=True)))


class Permissions:
    def __init__(self):
        self.role_to_ability = {}

    def add(self, ability: Ability):
        self.role_to_ability[ability.role] = ability

    def request_role(self, user: BaseUser, role):
        if role in user.roles:
            return self.role_to_ability.get(role)

    def copy(self):
        instance = Permissions()
        instance.key_to_roles = self.role_to_ability.copy()
        return instance

ability_all = Ability(None, {'*': '*'})
