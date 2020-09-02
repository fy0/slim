from typing import TYPE_CHECKING

from slim.exception import RecordNotFound, SyntaxException, InvalidParams, SQLOperatorInvalid, ColumnIsNotForeignKey, \
    ColumnNotFound, InvalidRole, PermissionDenied, FinishQuitException, SlimException, TableNotFound, \
    ResourceException, NotNullConstraintFailed, AlreadyExists, InvalidPostData, NoUserViewMixinException, \
    InvalidHeaders, InvalidToken
from slim.retcode import RETCODE

if TYPE_CHECKING:
    from slim.base.view import BaseView


class ErrorCatchContext:
    def __init__(self, view: "BaseView"):
        self.view = view

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val: Exception, exc_tb):
        # FinishQuitException
        if isinstance(exc_val, FinishQuitException):
            return True  # Finished, do nothing

        # SyntaxException
        elif isinstance(exc_val, SyntaxException):
            self.view.finish(RETCODE.FAILED, exc_val.args[0])

        # ParamsException
        elif isinstance(exc_val, SQLOperatorInvalid):
            self.view.finish(RETCODE.INVALID_PARAMS, "Invalid operator for select condition: %r" % exc_val.args[0])

        elif isinstance(exc_val, ColumnIsNotForeignKey):
            self.view.finish(RETCODE.INVALID_PARAMS, "This column is not a foreign key: %r" % exc_val.args[0])

        elif isinstance(exc_val, InvalidParams):
            if len(exc_val.args):
                self.view.finish(RETCODE.INVALID_PARAMS, exc_val.args[0])
            else:
                self.view.finish(RETCODE.INVALID_PARAMS)

        elif isinstance(exc_val, InvalidPostData):
            if len(exc_val.args):
                self.view.finish(RETCODE.INVALID_POSTDATA, exc_val.args[0])
            else:
                self.view.finish(RETCODE.INVALID_POSTDATA)

        elif isinstance(exc_val, InvalidHeaders):
            if len(exc_val.args):
                self.view.finish(RETCODE.INVALID_HEADERS, exc_val.args[0])
            else:
                self.view.finish(RETCODE.INVALID_HEADERS)

        # ResourceException
        elif isinstance(exc_val, TableNotFound):
            self.view.finish(RETCODE.FAILED, exc_val.args[0])

        elif isinstance(exc_val, ColumnNotFound):
            self.view.finish(RETCODE.FAILED, exc_val.args[0], msg='Column not found')

        elif isinstance(exc_val, RecordNotFound):
            if len(exc_val.args) > 0:
                self.view.finish(RETCODE.NOT_FOUND, 'Nothing found from table %r' % exc_val.args[0])
            else:
                self.view.finish(RETCODE.NOT_FOUND, 'Nothing found from table %r' % self.view.table_name)

        elif isinstance(exc_val, NotNullConstraintFailed):
            self.view.finish(RETCODE.INVALID_POSTDATA, 'NOT NULL constraint failed')

        elif isinstance(exc_val, AlreadyExists):
            self.view.finish(RETCODE.ALREADY_EXISTS)

        elif isinstance(exc_val, ResourceException):
            self.view.finish(RETCODE.FAILED, exc_val.args[0])

        # PermissionException
        elif isinstance(exc_val, InvalidToken):
            self.view.finish(RETCODE.INVALID_TOKEN, "Invalid user token")

        elif isinstance(exc_val, InvalidRole):
            self.view.finish(RETCODE.INVALID_ROLE, "Invalid role: %r" % exc_val.args[0])

        elif isinstance(exc_val, PermissionDenied):
            if len(exc_val.args):
                self.view.finish(RETCODE.PERMISSION_DENIED, exc_val.args[0])
            else:
                self.view.finish(RETCODE.PERMISSION_DENIED)

        # others
        elif isinstance(exc_val, SlimException):
            self.view.finish(RETCODE.FAILED)

        else:
            return  # 异常会传递出去

        return True
