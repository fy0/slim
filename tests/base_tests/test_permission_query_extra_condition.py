import pytest

from slim.base.permission import A, Ability, DataRecord, Permissions
from slim.base.sqlquery import SQLQueryInfo, SQL_OP
from slim.exception import PermissionDenied

ab = Ability({
    'user': {
        'username': {A.QUERY, A.READ},
        'nickname': {A.QUERY, A.READ, A.QUERY_EX},
        'password': {A.QUERY},

        'phone': {A.READ},
    }
})


def test_query_condition_add1():
    """
    测试添加单个条件
    :return:
    """
    ab1 = Ability({}, based_on=ab)
    ab1.add_query_condition('user', ['phone', '>=', '123456'])

    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('username', '=', 'b')

    assert sqi.conditions[-1] == ['username', SQL_OP.EQ, 'b']
    sqi.check_query_permission_full(None, 'user', ab1, None)
    assert sqi.conditions[-1] == ['phone', SQL_OP.GE, '123456']


def test_query_condition_add2():
    """
    测试添加多个条件
    """
    ab2 = Ability({}, based_on=ab)
    ab2.add_query_condition('user', [
        ['username', 'like', '1%'],
        ['nickname', 'like', '1%'],
    ])

    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('username', '=', 'b')
    sqi.check_query_permission_full(None, 'user', ab2, None)
    assert sqi.conditions == [['username', SQL_OP.EQ, 'b'], ['username', SQL_OP.LIKE, '1%'], ['nickname', SQL_OP.LIKE, '1%']]


def test_query_add_func():
    ab1 = Ability({}, based_on=ab)

    def func1(ability: Ability, user, query: 'SQLQueryInfo', view: "AbstractSQLView"):
        query.add_condition('nickname', '=', 'aa')

    ab1.add_query_condition('user', func=func1)

    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('username', '=', 'b')
    sqi.check_query_permission_full(None, 'user', ab1, None)
    assert sqi.conditions == [['username', SQL_OP.EQ, 'b'], ['nickname', SQL_OP.EQ, 'aa'],]

    ab2 = Ability({}, based_on=ab)

    def func2(ability: Ability, user, query: 'SQLQueryInfo'):
        query.add_condition('nickname', '=', 'aa')

    ab2.add_query_condition('user', func=func2)

    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('username', '=', 'b')
    sqi.check_query_permission_full(None, 'user', ab2, None)
    assert sqi.conditions == [['username', SQL_OP.EQ, 'b'], ['nickname', SQL_OP.EQ, 'aa'],]


def test_query_condition_clear_by_check():
    """
    查询权限被检查机制清空的情况
    :return:
    """
    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('phone', '=', 'b')
    sqi.parse_then_add_condition('phone', '>', '100')

    # # 所有查询条件都被权限机制清空
    with pytest.raises(PermissionDenied) as excinfo:
        sqi.check_query_permission_full(None, 'user', ab, None, ignore_error=True)

    assert sqi.conditions == []

    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('phone', '=', 'b')
    sqi.parse_then_add_condition('username', '=', 'b')
    sqi.check_query_permission_full(None, 'user', ab, None, ignore_error=True)

    with pytest.raises(PermissionDenied) as excinfo:
        sqi = SQLQueryInfo()
        sqi.select = sqi.parse_select('username, nickname, password')
        sqi.parse_then_add_condition('phone', '=', 'b')
        sqi.parse_then_add_condition('username', '=', 'b')
        sqi.check_query_permission_full(None, 'user', ab, None, ignore_error=False)


if __name__ == '__main__':
    test_query_condition_clear_by_check()
