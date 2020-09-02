from model.user import POST_STATE
from permissions.roles import *


post_state_conditions = [
    ('state', '>', POST_STATE.DEL),
]


def add_post_visible_limit(table):
    visitor.add_query_condition(table, post_state_conditions)
    user.add_query_condition(table, post_state_conditions)
