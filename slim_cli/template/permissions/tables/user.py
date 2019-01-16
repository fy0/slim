from model.user import POST_STATE
from permissions.roles import *
from permissions.tables._vars import add_post_visible_limit
from slim.base.permission import Ability, A, DataRecord
from slim.base.sqlquery import SQLQueryInfo, SQL_OP


# 如果查询的是自己，多附带部分信息
def func(ability: Ability, user, query: 'SQLQueryInfo'):
    for i in query.conditions.find('id'):
        if i[1] == SQL_OP.EQ and i[2] == user.id.hex():
            query.select.add('email')
            query.select.add('token_time')


normal_user.add_query_condition('user', func=func)


# 阻止其他人写入自己的个人资料
def check_is_me(ability, user, action, record: DataRecord, available_columns: list):
    if user:
        if record.get('id') != user.id:
            available_columns.clear()
    return True


visitor.add_record_check((A.WRITE,), 'user', func=check_is_me)

# 不允许查询删除状态的信息
add_post_visible_limit('user')
