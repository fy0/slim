
class SlimException(Exception):
    pass


class NoUserViewMixinException(SlimException):
    pass


class SyntaxException(SlimException):
    pass


class InvalidParams(SlimException):
    pass


class SQLOperatorInvalid(InvalidParams):
    pass


class ColumnIsNotForeignKey(InvalidParams):
    # 外键只有读取一种情况，因此作为 ParamsException 而不是 ResourceException
    pass


class InvalidPostData(SlimException):
    pass


class ResourceException(SlimException):
    pass


class TableNotFound(ResourceException):
    pass


class ColumnNotFound(ResourceException):
    pass


class RecordNotFound(ResourceException):
    pass


class AlreadyExists(ResourceException):
    pass


class NotNullConstraintFailed(ResourceException):
    pass


class PermissionException(SlimException):
    pass


class InvalidRole(PermissionException):
    pass


class PermissionDenied(SlimException):
    pass


class FinishQuitException(SlimException):
    pass
