from permissions.roles import *
from permissions.tables import *


def permissions_add_all(permission):
    permission.add(visitor)
    permission.add(normal_user)
