import pytest
from peewee import SqliteDatabase, Model, TextField

from slim import Application, ALL_PERMISSION
from slim.support.peewee import PeeweeView

from slim.base.sqlquery import SQLQueryInfo, SQLQueryOrder, ALL_COLUMNS, SQL_OP
from slim.exception import SyntaxException, InvalidParams, ColumnNotFound
from slim.tools.test import make_mocked_view, make_mocked_request

pytestmark = [pytest.mark.asyncio]
app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)
db = SqliteDatabase(":memory:")


async def test_new():
    sqi = SQLQueryInfo()


async def test_order():
    assert SQLQueryInfo.parse_order('a') == []
    assert SQLQueryInfo.parse_order('a,b,c') == []
    assert SQLQueryInfo.parse_order('a, b, c') == []
    assert SQLQueryInfo.parse_order('a, b,   c') == []
    assert SQLQueryInfo.parse_order('a, b,') == []
    assert SQLQueryInfo.parse_order('a.asc') == [SQLQueryOrder('a', 'asc')]
    assert SQLQueryInfo.parse_order('a.AsC') == [SQLQueryOrder('a', 'asc')]
    assert SQLQueryInfo.parse_order('a.asc, b,') == [SQLQueryOrder('a', 'asc')]
    assert SQLQueryInfo.parse_order('a.asc,b,c.desc') == [SQLQueryOrder('a', 'asc'), SQLQueryOrder('c', 'desc')]

    try:
        SQLQueryInfo.parse_order('a.a.a')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    try:
        SQLQueryInfo.parse_order('a.?sc')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    sqi = SQLQueryInfo()
    sqi.set_orders([])

    try:
        sqi.set_orders([1])
        assert False
    except Exception as e:
        assert isinstance(e, AssertionError)

    sqi.set_orders([SQLQueryOrder('A', 'asc')])
    assert sqi.orders == [SQLQueryOrder('A', 'asc')]


async def test_select():
    assert SQLQueryInfo.parse_select('aa') == {'aa'}
    assert SQLQueryInfo.parse_select('aa,') == {'aa'}
    assert SQLQueryInfo.parse_select('aa,bbb') == {'aa', 'bbb'}
    assert SQLQueryInfo.parse_select('aa, bbb') == {'aa', 'bbb'}
    assert SQLQueryInfo.parse_select('aa,  \nbbb') == {'aa', 'bbb'}
    assert SQLQueryInfo.parse_select('*') == ALL_COLUMNS
    try:
        SQLQueryInfo.parse_select(',')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)
    try:
        SQLQueryInfo.parse_select(',,,')
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    sqi = SQLQueryInfo()
    try:
        sqi.set_select([1, 2, '3'])
        assert False
    except Exception as e:
        assert isinstance(e, AssertionError)

    try:
        sqi.set_select(None)
        assert False
    except Exception as e:
        assert isinstance(e, InvalidParams)

    assert sqi.set_select(ALL_COLUMNS) is None
    assert sqi.set_select(['1', '2', '3']) is None
    assert sqi.set_select({'1', '2', '3'}) is None


async def test_very_simple_condition():
    sqi = SQLQueryInfo()
    sqi.parse_then_add_condition('a', '=', 'b')
    assert sqi.conditions[0] == ['a', SQL_OP.EQ, 'b']

    sqi = SQLQueryInfo()
    sqi.parse_then_add_condition('a', 'like', 'b')
    assert sqi.conditions[0] == ['a', SQL_OP.LIKE, 'b']

    for i in SQL_OP.ALL:
        sqi = SQLQueryInfo()
        if i in SQL_OP.IN.value or i in SQL_OP.CONTAINS.value or i in SQL_OP.CONTAINS_ANY.value:
            sqi.parse_then_add_condition('a', i, '[1,2]')
            assert sqi.conditions[0] == ['a', SQL_OP.txt2op[i], [1,2]]
        else:
            sqi.parse_then_add_condition('a', i, 'b')
            assert sqi.conditions[0] == ['a', SQL_OP.txt2op[i], 'b']


class ATestModel(Model):
    name = TextField()


@app.route.view('test1')
class ATestView(PeeweeView):
    model = ATestModel


async def test_condition_bind():
    sqi = SQLQueryInfo()
    sqi.parse_then_add_condition('name', '=', '1')
    view: PeeweeView = await make_mocked_view(app, ATestView, 'GET', '/api/test1')
    sqi.bind(view)


async def test_condition_bind_error_column_not_found():
    sqi = SQLQueryInfo()
    sqi.parse_then_add_condition('name1', '=', '1')
    view: PeeweeView = await make_mocked_view(app, ATestView, 'GET', '/api/test1')

    with pytest.raises(ColumnNotFound) as e:
        sqi.bind(view)

    assert 'name1' in e.value.args[0]


async def test_condition_bind_error_convert_failed():
    sqi = SQLQueryInfo()
    sqi.parse_then_add_condition('name', '=', {})
    view: PeeweeView = await make_mocked_view(app, ATestView, 'GET', '/api/test1')

    with pytest.raises(InvalidParams) as e:
        sqi.bind(view)

    assert 'name' in e.value.args[0]
    assert "Couldn't interpret" in str(e.value)


async def test_condition_bind_error_in_or_not_in_value():
    sqi = SQLQueryInfo()

    with pytest.raises(InvalidParams) as e:
        sqi.parse_then_add_condition('name', 'in', [1, 2])
        assert 'name' in e.value.args[0]
