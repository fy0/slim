import pytest
from slim.support.peewee import PeeweeView
from peewee import *
from slim import Application, ALL_PERMISSION
from slim.utils import get_ioloop
from tests.tools import make_mocked_view_instance


pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class ATestModel(Model):
    info = BlobField()

    class Meta:
        table_name = 'test'
        database = db


db.create_tables([ATestModel])


@app.route('test')
class ATestView(PeeweeView):
    LIST_PAGE_SIZE = -1

    model = ATestModel


async def test_view_list_bug():
    """
    当 LIST_PAGE_SIZE为-1 时，如果表中无数据，由于分页大小会自动设置为与查出的数据数量一致（为0），计算页数时会出现除以0的问题
    """
    view: PeeweeView = await make_mocked_view_instance(app, ATestView, 'POST', '/api/list/1')
    await view.list()  # BUG 情况会抛出一个 ZeroDivisionError


if __name__ == '__main__':
    loop = get_ioloop()
    loop.run_until_complete(test_view_list_bug())
