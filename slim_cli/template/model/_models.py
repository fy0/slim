from model import db
from model.example import Example
from model.user import User
from model.user_token import UserToken

db.connect()
db.create_tables([Example, User, UserToken], safe=True)
