import pytest

from slim.base._view.base_view import BaseView
from slim.base._view.err_catch_context import ErrorCatchContext
from slim.exception import FinishQuitException, SyntaxException, SQLOperatorInvalid, ColumnIsNotForeignKey, \
    InvalidParams, InvalidPostData, InvalidHeaders, TableNotFound, ColumnNotFound, RecordNotFound, \
    NotNullConstraintFailed, AlreadyExists, ResourceException, InvalidToken, InvalidRole, PermissionDenied, \
    SlimException

exceptions_catch = [
    # FinishQuitException
    [FinishQuitException],

    # SyntaxException
    [SyntaxException, 'test'],

    # ParamsException
    [SQLOperatorInvalid, 'test'],
    [ColumnIsNotForeignKey, 'test'],
    [InvalidParams],
    [InvalidParams, 'test'],
    [InvalidPostData],
    [InvalidPostData, 'test'],
    [InvalidHeaders],
    [InvalidHeaders, 'test'],

    # ResourceException
    [TableNotFound, 'test'],
    [ColumnNotFound, 'test'],
    [RecordNotFound],
    [RecordNotFound, 'test'],

    [NotNullConstraintFailed],
    [AlreadyExists],
    [ResourceException, 'test'],

    # PermissionException
    [InvalidToken],
    [InvalidRole, 'test'],
    [PermissionDenied],
    [PermissionDenied, 'test'],

    # others
    [SlimException]
]


@pytest.mark.parametrize('params', exceptions_catch)
def test_err_catch_context_catch(params):
    view = BaseView()
    view.table_name = 'fake_table'
    exception_cls = params[0]
    with ErrorCatchContext(view):
        args = params[1:]
        raise exception_cls(*args)

    if exception_cls != FinishQuitException:
        assert view.response


def test_err_catch_context_catch_no_catch():
    with pytest.raises(ZeroDivisionError):
        with ErrorCatchContext(BaseView()):
            print(1 / 0)
