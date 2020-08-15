import pytest
from peewee import Model, BlobField
from playhouse.postgres_ext import ArrayField

from slim import Application, ALL_PERMISSION
from slim.base.permission import Ability
from slim.base.sqlquery import SQLQueryInfo, SQL_OP
from slim.exception import InvalidParams
from slim.support.peewee import PeeweeView

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456')

app.permission.add(None, Ability({
    '*': '*'
}))


class ATestModel(Model):
    name = ArrayField(BlobField)

    class Meta:
        table_name = 'topic'


@app.route.view('test1')
class ATestView(PeeweeView):
    model = ATestModel


ATestView.ability = Ability({
    '*': '*'
})
app.prepare()


async def test_pg_array_contains_bad_type():
    view = ATestView(app)
    sqi = SQLQueryInfo()
    with pytest.raises(InvalidParams):
        sqi.add_condition('name', SQL_OP.CONTAINS, b'aa')
        sqi.bind(view)


async def test_pg_array_contains_bad_type2():
    view = ATestView(app)
    sqi = SQLQueryInfo()
    with pytest.raises(InvalidParams):
        sqi.add_condition('name', SQL_OP.CONTAINS, 11)
        sqi.bind(view)


async def test_pg_array_contains_bad_type3():
    view = ATestView(app)
    sqi = SQLQueryInfo()
    with pytest.raises(InvalidParams):
        sqi.add_condition('name', SQL_OP.CONTAINS, [b'aa', 11])
        sqi.bind(view)


async def test_pg_array_contains_ok():
    view = ATestView(app)
    sqi = SQLQueryInfo()
    sqi.add_condition('name', SQL_OP.CONTAINS, [b'aa'])
    sqi.bind(view)


async def test_pg_array_contains_ok2():
    view = ATestView(app)
    sqi = SQLQueryInfo()
    sqi.add_condition('name', SQL_OP.CONTAINS, [b'aa', b'bb'])
    sqi.bind(view)
