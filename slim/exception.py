
class SlimException(Exception):
    pass


class InvalidRouteUrl(SlimException):
    pass


class StaticDirectoryNotExists(SlimException):
    pass


class NoUserViewMixinException(SlimException):
    pass


class SyntaxException(SlimException):
    pass


class InvalidParams(SlimException):
    pass


class InvalidHeaders(SlimException):
    pass


class SQLOperatorInvalid(InvalidParams):
    pass


class ColumnIsNotForeignKey(InvalidParams):
    # 外键只有读取一种情况，因此作为 ParamsException 而不是 ResourceException
    pass


class InvalidResponse(SlimException):
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


class InvalidToken(PermissionException):
    pass


class InvalidRole(PermissionException):
    pass


class PermissionDenied(PermissionException):
    pass


class FinishQuitException(SlimException):
    pass
