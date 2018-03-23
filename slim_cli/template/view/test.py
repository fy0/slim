from app import app
from slim.support.peewee import PeeweeView
from slim.base.permission import Permissions
from model.test import Test
from view.permissions import visitor, normal_user


@app.route('test')
class TestView(PeeweeView):
    model = Test

    @classmethod
    def permission_init(cls):
        permission: Permissions = cls.permission
        permission.add(visitor)
        permission.add(normal_user)
