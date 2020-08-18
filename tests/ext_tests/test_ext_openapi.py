import peewee
import pytest
from peewee import SqliteDatabase

from slim import Application, ALL_PERMISSION
from slim.ext.openapi.main import get_openapi
from slim.support.peewee import PeeweeView

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class ATestModel(peewee.Model):
    info = peewee.BlobField()

    class Meta:
        table_name = 'test'
        database = db


@app.route.view('test')
class ATestView(PeeweeView):
    model = ATestModel


app.prepare()


async def test_openapi_gen_peewee_view_simple():
    get_openapi(app)
