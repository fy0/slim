from app import app
from slim.support.peewee import PeeweeView
from model.example import Example


@app.route('example')
class ExampleView(PeeweeView):
    model = Example
