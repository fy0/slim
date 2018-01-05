from app import app
from slim.support.peewee import PeeweeView
from model.test import Test


@app.route('test')
class TestView(PeeweeView):
    model = Test
