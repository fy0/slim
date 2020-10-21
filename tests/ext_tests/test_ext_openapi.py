import peewee
import pytest
from peewee import SqliteDatabase

from slim import Application
from slim.ext.openapi.main import get_openapi

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456')
db = SqliteDatabase(":memory:")


class ATestModel(peewee.Model):
    info = peewee.BlobField()

    class Meta:
        table_name = 'test'
        database = db


# @app.route.view('test')
# class ATestView(PeeweeView):
#     model = ATestModel


app.prepare()


async def test_openapi_gen_peewee_view_simple():
    # get_openapi(app)
    pass
