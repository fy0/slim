from ...base.permission import Permission


class AsyncpgPermission(Permission):
    @classmethod
    def _check_permission(cls, role, res, request, args, orders, ext):
        # need override
        return True
