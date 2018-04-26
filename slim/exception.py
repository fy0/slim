
class SlimException(Exception):
    pass


class SyntaxException(SlimException):
    pass


class ParamsException(SlimException):
    pass


class SQLOperatorInvalid(ParamsException):
    pass


class ColumnIsNotForeignKey(ParamsException):
    # 外键只有读取一种情况，因此作为 ParamsException 而不是 ResourceException
    pass


class InvalidPostData(SlimException):
    pass


class ResourceException(SlimException):
    pass


class ColumnNotFound(ResourceException):
    pass


class RecordNotFound(ResourceException):
    pass


class PermissionException(SlimException):
    pass


class RoleNotFound(PermissionException):
    pass


class PermissionDenied(SlimException):
    pass


class FinishQuitException(SlimException):
    pass


class ValueHandleException(SlimException):
    pass
