
class SlimException(Exception):
    pass


class SyntaxException(SlimException):
    pass


class ParamsException(SlimException):
    pass


class SQLOperatorInvalid(ParamsException):
    pass


class ColumnNotFound(SlimException):
    pass


class RecordNotFound(SlimException):
    pass


class PermissionException(SlimException):
    pass


class RoleNotFound(PermissionException):
    pass


class ColumnIsNotForeignKey(SlimException):
    pass


class PermissionDeniedException(SlimException):
    pass


class ResourceException(SlimException):
    pass


class ValueHandleException(SlimException):
    pass
