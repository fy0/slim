
class USER_STATE:
    DEL = 0
    BAN = 30
    NORMAL = 50
    WRITER = 80
    ADMIN = 100


class PermissionItem:
    """ 权限级别项，用于描述单个用户组所拥有的权限 """
    def __init__(self, key, inherit_key=None, data=None, data2=None):
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
            new_data = inherit_item.copy()
            for k, v in old_data.items():
                if k not in new_data:
                    new_data[k] = v
            self.data = new_data

    def is_valid(self, request):
        """
        检查当前操作是否合法
        :param request: 
        :return: 
        """
        return True


class Permission:
    def __init__(self, resource):
        self.res = resource
        self.item_by_key = {}

        for item in self.items:
            if issubclass(type(item), PermissionItem):
                self.item_by_key[item.key] = item
                item.init(self)

    def current(self):
        return None

    def is_valid(self, name, request):
        return True

    items = [
        PermissionItem(USER_STATE.NORMAL, None, {
            'user': {
                'username': {
                    'allow': 'read',
                },
                'nickname': {
                    'allow': 'write',
                    'valid': ['aaa', 'bbb', 'ccc']  # 只在写入时进行检查
                }
            }
        }, {
            'name': {
                'get': 'none',
            },
            'user': 'none'
       }),
    ]
