import json


def _sql_escape(key: str):
    return json.dumps(key)


class BaseCompiler:
    def __init__(self):
        self.reset()

    def reset(self):
        self._tables = []
        self._wheres = []
        self._values = []
        self._tbl_dict = {}
        self._default_tbl = None
        self._extra = {}

    def _add_value(self, val, type_codec=None):
        item = '$%d' % (len(self._values) + 1)
        if type_codec: item += '::%s' % type_codec
        self._values.append(val)
        return item

    def where1(self, column, op, value, type_codec=None, *, table=None, group=None):
        table = table or self._default_tbl
        self._wheres.append([table, column, op, value, type_codec, group])
        return self

    def where_many(self, args, *, table=None):
        for column, op, value, type_codec, group in args:
            self.where1(column, op, value, type_codec, table=table, group=group)
        return self

    def set_default_table(self, tbl):
        self._default_tbl = tbl
        return self

    def _from_table(self, table: str, as_default: bool = False):
        self._tables = [table]
        if not self._default_tbl:
            self._default_tbl = table
        return self

    def _from_tables(self, tables: list, *, default_table=None):
        self._tables = tables
        if not self._default_tbl:
            self._default_tbl = tables[0]
        return self

    def set_ext(self, extra):
        self._extra = extra
        {
            '_root': {

            },
        }
        return self

    def _not_implemented(self):
        if False: return True # for warning fix
        raise NotImplementedError()

    def sql(self) -> str:
        return ''


class SelectCompiler(BaseCompiler):
    def reset(self):
        super().reset()
        self._query_count = False
        self._query_expr = '*'
        self._offset = None
        self._limit = None
        self._order_by = []

    def select_raw(self, val):
        self._query_expr = val
        return self

    def select_count(self, val=None):
        self._query_count = val or '*'
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
        self._order_by.append([table, column, order])
        return self

    def order_by_many(self, orders):
        for column, order, table in orders:
            self.order_by(column, order, table=table)
        return self

    def sql(self):
        self._tbl_dict = {}
        sql = ['select', self._query_expr, ]

        if self._tables:
            sql.append('from')
            for _, i in enumerate(self._tables):
                alias = 't%d' % (_ + 1)
                self._tbl_dict[i] = alias
                sql.extend([_sql_escape(i), 'as', _sql_escape(alias), ','])
            sql.pop()

        if self._wheres:
            sql.append('where')
            for table, column, op, value, type_codec, group in self._wheres:
                # "t1" . "col1" == $1
                sql.extend(
                    ['(', _sql_escape(self._tbl_dict[table]), '.', _sql_escape(column), op, self._add_value(value, type_codec),
                     ')', 'and'])
            sql.pop()

        if self._order_by and self._query_expr != 'count(1)':
            sql.append('order by')
            for table, column, order in self._order_by:
                # "t1" . "col1" [asc | desc]
                sql.extend([_sql_escape(self._tbl_dict[table]), '.', _sql_escape(column), order, ','])
            sql.pop()

        if self._offset is not None:
            sql.extend(['offset', self._add_value(self._offset)])

        if self._limit is not None:
            sql.extend(['limit', self._add_value(self._limit)])
        if self._query_count:
            sql.insert(0, 'select count(1) from (')
            sql.extend([')', 'as', 'q1'])

        return ' '.join(sql), self._values


SelectCompiler.from_table = SelectCompiler._from_table
SelectCompiler.from_tables = SelectCompiler._from_tables


class UpdateCompiler(BaseCompiler):
    def reset(self):
        super().reset()
        self._update_values = []

    def set_values(self, args, *, table=None):
        for column, value, type_codec in args:
            self.set_value(column, value, type_codec, table=table)
        return self

    def set_value(self, column, value, type_codec=None, *, table=None):
        table = table or self._default_tbl
        self._update_values.append([table, column, value, type_codec])
        return self

    def sql(self):
        self._tbl_dict = {}
        sql = ['update', self._tables[0], 'as', _sql_escape('t1')]
        self._tbl_dict[self._tables[0]] = 't1'

        if self._update_values:
            sql.append('set')
            for table, column, value, type_codec in self._wheres:
                # "t1" . "col1" = $1,
                sql.extend(
                    ['(', _sql_escape(self._tbl_dict[table]), '.', _sql_escape(column), '=', self._add_value(value, type_codec),
                     ')', ','])
            sql.pop()

        if self._wheres:
            sql.append('where')
            for table, column, op, value, type_codec, group in self._wheres:
                # "t1" . "col1" == $1
                sql.extend(
                    ['(', _sql_escape(self._tbl_dict[table]), '.', _sql_escape(column), op, self._add_value(value, type_codec),
                     ')', 'and'])
            sql.pop()

        return ' '.join(sql), self._values

    to_table = BaseCompiler._from_table
    _from_tables = BaseCompiler._not_implemented


class InsertCompiler(BaseCompiler):
    into_table = BaseCompiler._from_table
    into_tables = BaseCompiler._from_tables
