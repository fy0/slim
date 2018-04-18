
class SlimException(Exception):
    pass


class SyntaxException(SlimException):
    pass


class ParamsException(SlimException):
    pass


class ColumnNotFound(SlimException):
    pass


class ColumnIsNotForeignKey(SlimException):
    pass


class PermissionDeniedException(SlimException):
    pass


class ResourceException(SlimException):
    pass


class ValueHandleException(SlimException):
    pass
