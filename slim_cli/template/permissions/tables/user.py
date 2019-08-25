from permissions.roles import *
from permissions.tables._vars import add_post_visible_limit
from slim.base.permission import Ability, A, DataRecord
from slim.base.sqlquery import SQLQueryInfo, SQL_OP
from slim.utils import get_bytes_from_blob

TABLE_NAME = 'user'


# 如果查询的是自己，多附带部分信息
def func(ability: Ability, user, query: 'SQLQueryInfo'):
    for i in query.conditions.find('id'):
        if i[1] == SQL_OP.EQ and i[2] == get_bytes_from_blob(user.id):
            query.select.add('email')
            query.select.add('token_time')


normal_user.add_query_condition(TABLE_NAME, func=func)


# 阻止其他人写入自己的个人资料
def check_is_me(ability, user, action, record: DataRecord, available_columns: list):
    if user:
        if record.get('id') != user.id:
            available_columns.clear()
    return True


visitor.add_record_check((A.WRITE,), TABLE_NAME, func=check_is_me)

# 不允许查询删除状态的信息
add_post_visible_limit(TABLE_NAME)
