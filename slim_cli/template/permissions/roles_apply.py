from app import app
from permissions.roles import *
import permissions.tables

from .role_define import ACCESS_ROLE

app.permission.add(ACCESS_ROLE.VISITOR, visitor)
app.permission.add(ACCESS_ROLE.USER, user)
