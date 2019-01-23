from app import app
from permissions.roles import *
from permissions.tables import *


app.permission.add(visitor)
app.permission.add(normal_user)
