import os

from permissions.roles import *
from permissions.tables._vars import add_post_visible_limit
from slim.ext.permission import Ability, A, DataRecord
from slim.ext.sqlview.sqlquery import SQLQueryInfo, SQL_OP
from slim.utils import get_bytes_from_blob

TABLE_NAME = os.path.basename(__file__).split('.', 1)[0]


# 如果查询的是自己，多附带部分信息
def func(ability: Ability, user, query: 'SQLQueryInfo'):
    for i in query.conditions.find('id'):
        if i[1] == SQL_OP.EQ and i[2] == get_bytes_from_blob(user.id):
            query.select.add('email')
            query.select.add('token_time')


user.add_query_condition(TABLE_NAME, func=func)


# 阻止其他人写入自己的个人资料
def check_is_me(ability, user, action, record: DataRecord, available_columns: list):
    if user:
        if record.get('id') != user.id:
            available_columns.clear()
    return True


visitor.add_record_check((A.UPDATE,), TABLE_NAME, func=check_is_me)

# 不允许查询删除状态的信息
add_post_visible_limit(TABLE_NAME)
