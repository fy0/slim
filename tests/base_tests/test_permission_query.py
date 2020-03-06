from slim.base.permission import A, Ability, DataRecord, Permissions
from slim.base.sqlquery import SQLQueryInfo, SQL_OP

ab = Ability({
    'user': {
        'username': {A.QUERY, A.READ},
        'nickname': {A.QUERY, A.READ, A.QUERY_EX},
        'password': {A.QUERY},

        'phone': {A.READ},
    }
})


def test_query_filter():
    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('username', '=', 'b')
    sqi.parse_then_add_condition('nickname', '=', 'b')
    sqi.check_query_permission_full(None, 'user', ab, None)
    assert sqi.conditions == [['username', SQL_OP.EQ, 'b'], ['nickname', SQL_OP.EQ, 'b']]

    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('phone', '=', 'c')
    sqi.parse_then_add_condition('username', '=', 'b')
    sqi.parse_then_add_condition('username', 'like', 'b')
    sqi.parse_then_add_condition('nickname', '=', 'b')
    sqi.check_query_permission_full(None, 'user', ab, None)
    assert sqi.conditions == [['username', SQL_OP.EQ, 'b'], ['nickname', SQL_OP.EQ, 'b']]


def test_query_ex_filter():
    sqi = SQLQueryInfo()
    sqi.select = sqi.parse_select('username, nickname, password')
    sqi.parse_then_add_condition('username', 'like', 'b')
    sqi.parse_then_add_condition('nickname', 'like', 'b')
    sqi.check_query_permission_full(None, 'user', ab, None)
    assert sqi.conditions == [['nickname', SQL_OP.LIKE, 'b']]
