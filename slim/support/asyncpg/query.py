import json
import logging

logger = logging.getLogger(__name__)


class QueryException(Exception):
    pass


def _sql_escape(key: str):
    # TODO: 是否正确？
    return json.dumps(key)


def _expr(op, inv=False):
    if inv:
        def func(self, rhs):
            return ConditionExpression(rhs, op, self)
    else:
        def func(self, rhs):
            return ConditionExpression(self, op, rhs)
    return func


def _qexpr(op, inv=False):
    if inv:
        def func(self, rhs):
            return QueryExpression(rhs, op, self)
    else:
        def func(self, rhs):
            return QueryExpression(self, op, rhs)
    return func


class BaseExpression:
    def __init__(self, lhs, op, rhs, *, values=None):
        self.lhs = lhs
        self.op = op
        self.rhs = rhs
        self.values = values

    def __str__(self):
        if self.values:
            key = ' %s ' % self.op
            return key.join(map(str, self.values))
        return '%s %s %s' % (self.lhs, self.op, self.rhs)


class QueryExpression(BaseExpression):
    __add__ = _qexpr('+')
    __sub__ = _qexpr('-')
    __mul__ = _qexpr('*')
    __div__ = __truediv__ = _qexpr('/')

    __radd__ = _qexpr('+', inv=True)
    __rsub__ = _qexpr('-', inv=True)
    __rmul__ = _qexpr('*', inv=True)
    __rdiv__ = __rtruediv__ = _qexpr('/', inv=True)

    __and__ = _expr('and')
    __or__ = _expr('or')

    __rand__ = _expr('and', inv=True)
    __ror__ = _expr('or', inv=True)

    in_ = _qexpr('in')
    is_ = _qexpr('is')


class ConditionExpression(BaseExpression):
    __and__ = _expr('and')
    __or__ = _expr('or')

    __rand__ = _expr('and', inv=True)
    __ror__ = _expr('or', inv=True)


class Column:
    def __init__(self, column_name, type_codec=None, *, table=None):
        self.column_name = column_name
        self.type_codec = type_codec
        self.table = table
        self.func = None

    def sum(self):
        self.func = 'sum'
        return self

    def count(self):
        self.func = 'count'
        return self

    __and__ = _expr('and')
    __or__ = _expr('or')
    __rand__ = _expr('and', inv=True)
    __ror__ = _expr('or', inv=True)

    __add__ = _qexpr('+')
    __sub__ = _qexpr('-')
    __mul__ = _qexpr('*')
    __div__ = __truediv__ = _qexpr('/')
    __radd__ = _qexpr('+', inv=True)
    __rsub__ = _qexpr('-', inv=True)
    __rmul__ = _qexpr('*', inv=True)
    __rdiv__ = __rtruediv__ = _qexpr('/', inv=True)

    in_ = _qexpr('in')
    is_ = _qexpr('is')

    def __repr__(self):
        if self.func:
            table = '"%s(%s)"' % (self.func, self.table)
        else:
            table = self.table
        return '"%s.%s"' % (table, self.column_name)


# noinspection PyAttributeOutsideInit
class BaseCompiler:
    def __init__(self, pv_params=False):
        self.pv_params = pv_params
        self.reset()

    def reset(self):
        self._tables = []
        self._wheres = []
        self._wheres_simple = []
        self._values = []
        self._tbl_dict = {}
        self._default_tbl = None
        self._extra = {}

    def _add_value(self, val, type_codec=None, *, op=None):
        if op in ('is', 'is not'):
            return 'null'

        if self.pv_params:
            item = '%s'
        else:
            item = '$%d' % (len(self._values) + 1)
            if type_codec:
                item += '::%s' % type_codec
            if op == 'in':
                # expression = any($1::mytype[])
                item = 'any(%s[])' % item
        self._values.append(val)
        return item

    def where(self, *args):
        self._wheres.extend(args)
        return self

    def simple_where_one(self, column, op, value, type_codec=None, *, table=None):
        table = table or self._default_tbl
        self._wheres_simple.append([table, column, op, value, type_codec])
        return self

    def simple_where_many(self, args_lst, *, table=None):
        for column, op, value, type_codec in args_lst:
            self.simple_where_one(column, op, value, type_codec, table=table)
        return self

    def set_default_table(self, tbl):
        self._default_tbl = tbl
        return self

    def _from_table(self, table: str):
        self._tables = [table]
        if not self._default_tbl:
            self._default_tbl = table
        return self

    def _from_tables(self, tables: list):
        self._tables = tables
        if not self._default_tbl:
            self._default_tbl = tables[0]
        return self

    def _not_implemented(self):
        if False: return True  # for warning fix
        raise NotImplementedError()

    def analysis(self):
        return {
            'table1': {
                'query': [],
                'read': [],
                'write': [],
            },
        }

    def _log_ret(self, *args):
        ret = tuple(args)
        logger.info(' '.join(map(str, ret)))
        return ret

    def sql(self) -> str:
        return ''


# noinspection PyAttributeOutsideInit,SqlNoDataSourceInspection
class SelectCompiler(BaseCompiler):
    def reset(self):
        super().reset()
        self._query_count = False
        self._query_expr = '*'
        self._query_columns = None
        self._offset = None
        self._limit = None
        self._order_by = []
        self._for_update_skip_locked = False

    def for_update_skip_locked(self):
        self._for_update_skip_locked = True
        return self

    def select(self, *columns: list):
        # ['table', 'column']
        # ['table', 'column', 'func']
        # Column Object
        self._query_columns = columns
        return self

    def select_raw(self, val):
        self._query_expr = val
        return self

    def select_count(self, val=None):
        self._query_count = val or '*'
        self.count()
        return self

    def select_ctid(self, val=None):
        self._query_count = val or 'ctid'
        self.count()
        return self

    def count(self):
        self._query_count = True
        return self

    def limit(self, val):
        self._limit = val
        return self

    def offset(self, val):
        self._offset = val
        return self

    def order_by(self, column, order='asc', *, table=None):
        table = table or self._default_tbl
        if order == 'default': order = 'asc'
        self._order_by.append([table, column, order])
        return self

    def order_by_many(self, orders):
        for i in orders:
            if len(i) == 2:
                # column, order
                self.order_by(i[0], i[1])
            elif len(i) == 3:
                # column, order, table
                self.order_by(i[0], i[1], table=i[2])
        return self

    def create_view_sql(self, view_name):
        sql = self.sql()
        lst = []

        if not self._query_columns:
            columns_txt = ''
        else:
            lst.append('(')
            for i in range(len(self._query_columns)):
                lst.extend(['c%d' % i, ','])
            lst.pop()
            lst.append(')')
            columns_txt = ' '.join(lst)
        return self._log_ret('create view %s%s as %s' % (_sql_escape(view_name), columns_txt, sql[0]), sql[1])

    def sql(self):
        self._tbl_dict = {}
        sql = ['select', ]

        if self._tables:
            for _, i in enumerate(self._tables):
                alias = 't%d' % (_ + 1)
                self._tbl_dict[i] = alias

        def type_to_sql(obj, obj_column_if_constant=None, expr_cls=QueryExpression):
            if type(obj) == Column:
                return column_to_sql(obj, expr_cls == ConditionExpression)
            elif type(obj) == expr_cls:
                return expr_to_sql(obj, expr_cls)
            elif isinstance(obj, BaseExpression):
                raise QueryException("[inner] Wrong expression type")
            else:
                return self._add_value(obj, obj_column_if_constant.type_codec)

        def column_to_sql(column: Column, ignore_func=False):
            base = _sql_escape(self._tbl_dict[column.table]) + '.' + _sql_escape(column.column_name)
            if (not ignore_func) and column.func:
                return column.func + '(' + base + ')'
            return base

        def expr_to_sql(expr: BaseExpression, expr_cls):
            if expr.values:
                # expr.values exists
                # type of args item is ConditionExpression
                op = ' %s ' % expr.op
                _expr_to_sql = lambda x: expr_to_sql(x, expr_cls)
                return '(' + op.join(map(_expr_to_sql, expr.values)) + ')'
            else:
                # expr.lhs is always column
                rhs = type_to_sql(expr.rhs, expr.lhs, expr_cls)
                return '(%s %s %s)' % (column_to_sql(expr.lhs), expr.op, rhs)

        if self._query_columns:
            def _valid_lst(column):
                if 2 <= len(column) <= 3:
                    if column[0] not in self._tbl_dict:
                        return
                    if len(column) == 3:
                        if column[2] not in ('sum', 'count'):
                            return
                    return True

            for i in self._query_columns:
                if isinstance(i, (list, tuple)):
                    if not _valid_lst(i):
                        raise QueryException('Invalid object for select')
                    if len(i) == 3:
                        sql.append(i[2]+'(')
                    sql.extend([_sql_escape(self._tbl_dict[i[0]]), '.', _sql_escape(i[1])])
                    if len(i) == 3:
                        sql.append(')')
                    sql.append(',')
                elif isinstance(i, (QueryExpression, Column)):
                    sql.extend([type_to_sql(i, expr_cls=QueryExpression), ','])
                else:
                    self._add_value(i)
            sql.pop()
        else:
            sql.append(self._query_expr)

        if self._tables:
            sql.append('from')
            for _, i in enumerate(self._tables):
                alias = 't%d' % (_ + 1)
                sql.extend([_sql_escape(i), 'as', _sql_escape(alias), ','])
            sql.pop()

        if self._wheres or self._wheres_simple:
            sql.append('where')

        if self._wheres:
            for i in self._wheres:
                if type(i) == ConditionExpression:
                    sql.extend([expr_to_sql(i, ConditionExpression), 'and'])
                else:
                    raise QueryException('Invalid condition')
            sql.pop()

        if self._wheres_simple:
            if self._wheres: sql.append('and')
            for table, column, op, value, type_codec in self._wheres_simple:
                # "t1" . "col1" == $1
                _op = '=' if op == 'in' else op
                sql.extend(
                    ['(', _sql_escape(self._tbl_dict[table]), '.', _sql_escape(column), _op, self._add_value(value, type_codec, op=op),
                     ')', 'and'])
            sql.pop()

        if self._order_by and self._query_expr != 'count(1)':
            sql.append('order by')
            for table, column, order in self._order_by:
                # "t1" . "col1" [asc | desc]
                sql.extend([_sql_escape(self._tbl_dict[table]), '.', _sql_escape(column), order, ','])
            sql.pop()

        if self._for_update_skip_locked:
            sql.append('FOR UPDATE SKIP LOCKED')

        if self._offset is not None:
            sql.extend(['offset', self._add_value(self._offset)])

        if self._limit is not None:
            sql.extend(['limit', self._add_value(self._limit)])

        if self._query_count:
            sql.insert(0, 'select count(1) from (')
            sql.extend([')', 'as', 'q1'])

        return self._log_ret(' '.join(sql), self._values)

    from_table = BaseCompiler._from_table
    from_tables = BaseCompiler._from_tables


class UpdateCompiler(BaseCompiler):
    to_table = BaseCompiler._from_table
    _from_tables = BaseCompiler._not_implemented

    def reset(self):
        super().reset()
        self._update_values = []

    def set_values(self, values):
        for column, value in values.items():
            self.set_value(column, value)
        return self

    def set_value(self, column, value, type_codec=None):
        table = self._default_tbl
        self._update_values.append([column, value, type_codec])
        return self

    def sql(self):
        self._tbl_dict = {}
        sql = ['update', _sql_escape(self._tables[0]), 'as', _sql_escape('t1')]
        self._tbl_dict[self._tables[0]] = 't1'

        if self._update_values:
            sql.append('set')
            for column, value, type_codec in self._update_values:
                # "col1" = $1,
                sql.extend([_sql_escape(column), '=', self._add_value(value, type_codec), ','])
            sql.pop()

        if self._wheres_simple:
            sql.append('where')
            for table, column, op, value, type_codec in self._wheres_simple:
                # "t1" . "col1" == $1
                sql.extend(
                    ['(', _sql_escape(self._tbl_dict[table]), '.', _sql_escape(column), op, self._add_value(value, type_codec),
                     ')', 'and'])
            sql.pop()

        return self._log_ret(' '.join(sql), self._values)


# noinspection PyAttributeOutsideInit
class InsertCompiler(BaseCompiler):
    into_table = BaseCompiler._from_table
    _from_tables = BaseCompiler._not_implemented
    simple_where_one = BaseCompiler._not_implemented
    simple_where_many = BaseCompiler._not_implemented

    def reset(self):
        super().reset()
        self._update_values = []
        self.is_returning = False

    def set_values(self, values):
        for column, value in values.items():
            self.set_value(column, value)
        return self

    def set_value(self, column, value, type_codec=None):
        table = self._default_tbl
        self._update_values.append([column, value, type_codec])
        return self

    def returning(self):
        self.is_returning = True
        return self

    def sql(self):
        self._tbl_dict = {}
        sql = ['insert into', _sql_escape(self._tables[0]), 'as', _sql_escape('t1')]
        self._tbl_dict[self._tables[0]] = 't1'

        if self._update_values:
            sql.append('(')
            for column, value, type_codec in self._update_values:
                sql.extend([_sql_escape(column), ','])
            sql.pop()
            sql.append(')')

            sql.append('values')
            sql.append('(')
            for column, value, type_codec in self._update_values:
                sql.extend([self._add_value(value, type_codec), ','])
            sql.pop()
            sql.append(')')

        if self.is_returning:
            sql.append('returning *')

        return self._log_ret(' '.join(sql), self._values)


_operator_map = {
    # '+': '__pos__',
    # '-': '__neg__',
    '=': '__eq__',
    '!=': '__ne__',
    '<>': '__ne__',
    '<': '__lt__',
    '<=': '__le__',
    '>': '__gt__',
    '>=': '__ge__',
    'eq': '__eq__',
    'ne': '__ne__',
    'ge': '__ge__',
    'gt': '__gt__',
    'le': '__le__',
    'lt': '__lt__',
    'in': 'in_',
    'is': 'is_',

    'and': '__and__',
    'or': '__or__',
}


def parse_query_by_json(data):
    """
    ['and',
        ['==', 't1', 'col1', val1],
        ['!=', 't1', 'col2', 't2', 'col2'],
        ['and',
            ['==', 't1', 'col3', val3],
            ['!=', 't2', 'col4', val4],
        ]
    ]
    :return:
    :param data: 
    :return: 
    """
    data = json.loads(data)

    for i in ('tables', 'columns', 'conditions'):
        if i not in data:
            raise QueryException("query: %s not found" % i)

    tables = data['tables']
    columns = data['columns']
    conditions = data['conditions']

    def parse_stmt(s, expr_cls, all_op, multi_items_op):
        if len(s) == 0:
            return []

        if s[0] in all_op:
            if s[0] in multi_items_op:
                values = []
                for i in s[1:]:
                    values.append(parse_stmt(i, expr_cls, all_op, multi_items_op))
                return expr_cls(None, s[0], None, values=values)
            else:
                if len(s) == 5:
                    # t1.c1 == t2.c2
                    lhs = Column(s[2], table=s[1])
                    rhs = Column(s[4], table=s[3])
                    if (s[1] not in tables) or (s[3] not in tables):
                        raise QueryException('Bad query')
                    return expr_cls(lhs, s[0], rhs)
                else:
                    # t1.c1 == val
                    lhs = Column(s[2], table=s[1])
                    if s[1] not in tables:
                        raise QueryException('Bad query')
                    return expr_cls(lhs, s[0], s[3])
        else:
            raise QueryException('Bad query')

    query_op = ('+', '-', '*', '/')
    query_columns = []

    for i in columns:
        if len(i) == 2:
            query_columns.append(Column(i[1], table=i[0]))
        else:
            query_columns.append(parse_stmt(i, QueryExpression, query_op, query_op))
    wheres = parse_stmt(conditions, ConditionExpression, _operator_map, ('and', 'or',))

    return {
        'tables': tables,
        'columns': query_columns,
        'wheres': wheres,
    }


'''
a = parse_query_by_json({
    'columns': [],
    'conditions': ['and',
        ['=', 't1', 'col1', 1],
        ['!=', 't1', 'col2', 't2', 'col2'],
        ['and',
            ['==', 't1', 'col3', '33'],
            ['!=', 't2', 'col4', '44'],
        ]
    ],
    'tables': ['t1', 't2']
})

print(str(a))
'''


#sc = SelectCompiler()
#sc.select().from_table("common_file").simple_where_one('state', 'is', 40).simple_where_one('state', '=', 40)
