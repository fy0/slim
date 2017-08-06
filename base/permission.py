from mapi.utils import _MetaClassForInit, RegexPatternType


class USER_ROLE:
    BAN = 30
    NORMAL = 50
    NORMAL_OWNER = 60
    EDITOR = 80
    ADMIN = 100


class PermissionItem:
    """ 权限级别项，用于描述单个用户组所拥有的权限 """
    def __init__(self, key, inherit_key=None, data=None):
        """
        :param key: 指代此级权限的键 
        :param inherit_key: 
        :param data: 对于data的设定为，如果data是字符串，那么必须是 read write none 三者之一，对整个表有效。
                      如果data是dict，那么其中的每一列分别起效。
        """
        self.key = key
        self.inherit = inherit_key
        self.data = data or {}

    def init(self, permission):
        """
        初始化，由父级进行调用
        :param permission: 父级对象
        :return: 无
        """
        if self.inherit is not None:
            inherit_item = permission.item_by_key[self.inherit]
            old_data = self.data
            new_data = inherit_item.data.copy()
            for k, v in old_data.items():
                if k not in new_data:
                    new_data[k] = v
            self.data = new_data


class Permission(metaclass=_MetaClassForInit):
    items = []
    item_by_key = {}

    @classmethod
    def init(cls):
        cls.item_by_key = {}
        for item in cls.items:
            if issubclass(type(item), PermissionItem):
                cls.item_by_key[item.key] = item
                item.init(cls)

    @classmethod
    def load_roles(cls, request) -> (tuple, list):
        # need override
        return USER_ROLE.NORMAL, USER_ROLE.NORMAL_OWNER

    @classmethod
    def _check_permission(cls, role, res, request, args, orders, ext):
        # need override
        return True

    @classmethod
    def _check_select_with_role(cls, role, res, request, args, orders, ext) -> (list, tuple):
        fails = []
        columns_for_read = []

        item = cls.item_by_key[role]
        table_permission = None

        # get permission dict
        if res.table_name in item.data:
            table_permission = item.data[res.table_name]
        else:
            for k, v in item.data.items():
                if isinstance(k, RegexPatternType):
                    if k.fullmatch(res.table_name):
                        table_permission = v

        if table_permission is None:
            fails.append('table not found: %s' % res.table_name)
        elif table_permission != '*':
            # query
            if table_permission['query'] is None:
                for column, op, value in args:
                    fails.append('query' % column)
                for column, order in orders:
                    fails.append('query: %s (order)' % column)

            elif table_permission['query'] != '*':
                for column, op, value in args:
                    if column not in table_permission['query']:
                        fails.append('query: %s' % column)

                for column, order in orders:
                    if column not in table_permission['query']:
                        fails.append('query: %s (order)' % column)

            # read
            if table_permission['read'] != '*':
                column_names = res.fields.keys()
                columns_for_read = column_names - table_permission['read']

        return fails, columns_for_read

    @classmethod
    def check_select(cls, res, request, args, orders, ext) -> (list, tuple):
        fails = []
        columns_for_read = []
        roles = cls.load_roles(request)
        role = min(roles)  # 只使用最低权限，应在参数中指定当前API使用的身份，以免出现高级用户每次请求总是返回过量敏感信息

        if 'with_role' in ext:
            if ext['with_role'] not in roles:
                fails.append('role request failed')
                return fails, columns_for_read
            else:
                role = ext['with_role']
                fails, columns_for_read = cls._check_select_with_role(role, res, request, args, orders, ext)

                if fails:
                    return fails, columns_for_read
                else:
                    if not cls._check_permission(role, res, request, args, orders, ext):
                        fails.append('role request failed')
                    return fails, columns_for_read

        fails, columns_for_read = cls._check_select_with_role(role, res, request, args, orders, ext)
        return fails, columns_for_read

    @classmethod
    def check_update(cls, res, request):
        pass


class FakePermission(Permission):
    @classmethod
    def check_select(cls, res, request, args, orders, ext) -> (list, tuple):
        return [], res.fields.keys()

