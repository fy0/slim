from model.user import POST_STATE
from slim.base.sqlquery import SQLQueryInfo, SQL_OP
from slim.base.permission import Ability
from permissions.roles import *


post_state_conditions = [
    ('state', '>', POST_STATE.DEL),
]


def add_post_visible_limit(table):
    visitor.add_query_condition(table, post_state_conditions)
    normal_user.add_query_condition(table, post_state_conditions)
