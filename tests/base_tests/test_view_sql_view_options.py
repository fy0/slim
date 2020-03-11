from peewee import SqliteDatabase, Model, BigIntegerField, TextField

from slim import Application, ALL_PERMISSION
from slim.base._view.view_options import SQLViewOptions
from slim.support.peewee import PeeweeView

app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


class Topic(Model):
    title = TextField(index=True)
    time = BigIntegerField(index=True)
    content = TextField()

    class Meta:
        database = db


def test_sql_view_options():
    class TopicView(PeeweeView):
        model = Topic
        options = SQLViewOptions(list_page_size=5)

    assert TopicView.LIST_PAGE_SIZE == 5
