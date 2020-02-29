from slim.support.peewee import PeeweeView

from app import app
from model.example import Example


@app.route.view('example')
class ExampleView(PeeweeView):
    model = Example
