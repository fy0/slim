from app import app
from permissions import permissions_add_all
from slim.support.peewee import PeeweeView
from model.example import Example


@app.route('example')
class ExampleView(PeeweeView):
    model = Example

    @classmethod
    def permission_init(cls):
        permissions_add_all(cls.permission)
