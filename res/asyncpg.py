import json
import asyncio
import asyncpg
from ..resource import Resource
from ..retcode import RETCODE
from ..utils import pagination_calc, ResourceException


def _sql_escape(key: str):
    return json.dumps(key)

_valid_sql_operator = {
    '=': '=',
    '==': '=',
    '!=': '!=',
    '<>': '<>',
    '<': '<',
    '<=': '<=',
    '>': '>',
    '>=': '>=',
    'eq': '=',
    'ne': '!=',
    'ge': '>=',
    'gt': '>',
    'le': '<=',
    'lt': '<'
}


class QueryCompiler:
    class SelectCompiler:
        def __init__(self):
            self.reset()

        def reset(self):
            self._query_expr = '*'
            self._tables = []
            self._wheres = []
            self._tb_dict = {}
            self._values = []
            self._offset = None
            self._limit = None
            self._order_by = []
            self._default_tbl = None

        def _add_value(self, val, type_codec=None):
            item = '$%d' % (len(self._values) + 1)
            if type_codec: item += '::%s' % type_codec
            self._values.append(val)
            return item

        def where1(self, column, op, value, type_codec=None, *, table=None):
            table = table or self._default_tbl
            self._wheres.append([table, column, op, value, type_codec])
            return self

        def where_many(self, args, *, table=None):
            for column, op, value, type_codec in args:
                self.where1(column, op, value, type_codec, table=table)
            return self

        def select_raw(self, val):
            self._query_expr = val
            return self

        def select_count(self):
            self._query_expr = 'count(1)'
            return self

        def set_default_table(self, tbl):
            self._default_tbl = tbl
            return self

        def from_table(self, table: str, as_default: bool = False):
            self._tables = [table]
            if not self._default_tbl:
                self._default_tbl = table
            return self

        def from_tables(self, tables: list, *, default_table=None):
            self._tables = tables
            if not self._default_tbl:
                self._default_tbl = tables[0]
            return self

        def limit(self, val):
            self._limit = val
            return self

        def offset(self, val):
            self._offset = val
            return self

        def order_by(self, column, ordering_suffix='ASC', *, table=None):
            table = table or self._default_tbl
            self._order_by.append([table, column, ordering_suffix])
            return self

        def sql(self):
            self._tb_dict = {}
            sql = ['select', self._query_expr, ]

            if self._tables:
                sql.append('from')
                for _, i in enumerate(self._tables):
                    alias = 't%d' % (_ + 1)
                    self._tb_dict[i] = alias
                    sql.extend([_sql_escape(i), 'as', _sql_escape(alias), ','])
                sql.pop()

            if self._wheres:
                sql.append('where')
                for table, column, op, value, type_codec in self._wheres:
                    # "t1" . "col1" == $1
                    sql.extend(
                        ['(', _sql_escape(self._tb_dict[table]), '.', _sql_escape(column), op, self._add_value(value, type_codec),
                         ')', 'and'])
                sql.pop()

            if self._order_by:
                sql.append('order by')
                for table, column, ordering_suffix in self._order_by:
                    # "t1" . "col1" [asc | desc]
                    sql.extend([_sql_escape(self._tb_dict[table]), '.', _sql_escape(column), ordering_suffix, ','])
                sql.pop()

            if self._offset is not None:
                sql.extend(['offset', self._add_value(self._offset)])

            if self._limit is not None:
                sql.extend(['limit', self._add_value(self._limit)])

            return ' '.join(sql), self._values


class AsyncpgResource(Resource):
    _field_query = '''SELECT a.attname as name, col_description(a.attrelid,a.attnum) as comment,pg_type.typname as typename, a.attnotnull as notnull
      FROM pg_class as c,pg_attribute as a inner join pg_type on pg_type.oid = a.atttypid 
      where c.relname = $1 and a.attrelid = c.oid and a.attnum>0;'''

    def __init__(self, conn, table_name):
        super().__init__()
        self.conn = conn
        self.table_name = table_name
        self.fields = None
        self.stmt_select = None
        self.stmt_select_count = None
        asyncio.get_event_loop().run_until_complete(self._fetch_fields())

    async def _fetch_fields(self):
        """
        fetch table schema from database
        :return: 
        """
        if self.table_name:
            info = await self.conn.fetch(self._field_query, self.table_name)
            ret = {}
            for i in info:
                ret[i['name']] = i
            self.fields = ret
            return ret

    def _query_convert(self, params):
        args = []
        for k, v in params.items():
            info = k.split('.', 1)

            if len(info) < 1:
                raise ResourceException('Invalid request parameter')

            field_name = info[0]
            op = '='

            if field_name not in self.fields:
                raise ResourceException('Field name not found: %s' % field_name)
            field = self.fields[field_name]
            type_codec = field['typename']

            # https://www.postgresql.org/docs/9.6/static/datatype.html
            # asyncpg/protocol/protocol.pyx
            if type_codec in ['int2', 'int4', 'int8']:
                type_codec = 'int'
                v = int(v)
            elif type_codec in ['float4', 'float8']:
                type_codec = 'float'
                v = float(v)

            if len(info) > 1:
                op = info[1]
                if op not in _valid_sql_operator:
                    raise ResourceException('Invalid operator: %s' % op)
                op = _valid_sql_operator[op]

            args.append([field_name, op, v, type_codec])
        return args

    async def get(self, request):
        sc = QueryCompiler.SelectCompiler()
        args = self._query_convert(request.query)
        sql = sc.select_raw('*').from_table(self.table_name).where_many(args).sql()
        ret = await self.conn.fetchrow(sql[0], *sql[1])

        if ret:
            self.finish(RETCODE.SUCCESS, json.dumps(list(ret.values())))
        else:
            self.finish(RETCODE.NOT_FOUND)

    async def set(self, request):
        item = self._get_one(request)
        if item:
            data = await request.post()
            for k, v in data.items():
                if k in self.fields:
                    setattr(item, k, self.query_and_store_handle(k, v))
            item.save()
            return self.finish(RETCODE.SUCCESS, item.to_dict())
        else:
            return self.finish(RETCODE.NOT_FOUND)

    async def new(self, request):
        item = self.model()
        if item:
            data = await request.post()
            for k, v in data.items():
                if k in self.fields:
                    setattr(item, k, v)
            item.save()
            self.finish(RETCODE.SUCCESS, item.to_dict())
        else:
            self.finish(RETCODE.NOT_FOUND)

    async def list(self, request):
        page = request.match_info.get('page', '1')
        size = request.match_info.get('size', None)

        if not page.isdigit():
            return self.finish(RETCODE.INVALID_PARAMS)

        if size and not size.isdigit():
            return self.finish(RETCODE.INVALID_PARAMS)

        page = int(page)
        size = int(size or self.LIST_PAGE_SIZE)

        sc = QueryCompiler.SelectCompiler()
        args = self._query_convert(request.query)
        sql = sc.select_count().from_table(self.table_name).where_many(args).sql()
        count = await self.conn.fetchval(sql[0], *sql[1])

        pg = pagination_calc(count, size, page)
        get_values = lambda x: list(x.values())

        sc.reset()
        sql = sc.select_raw('*').from_table(self.table_name).where_many(args).limit(size).offset(size * (page-1)).sql()
        ret = map(get_values, await self.conn.fetch(sql[0], *sql[1]))
        pg["items"] = list(ret)
        self.finish(RETCODE.SUCCESS, pg)


"""
sc = QueryCompiler.SelectCompiler()
print(sc.select_count().from_table('T596718ed293b327c5c00000b').sql())
print(sc.select_raw('*').from_table('T596718ed293b327c5c00000b')
      .where1('id', '=', 1)
      .where1('c1', '!=', '123')
      .offset(1)
      .limit(10)
      .order_by('c2')
      .sql())


async def main():
    sc = QueryCompiler.SelectCompiler()
    info = (sc.select_raw('*').from_table('T596718ed293b327c5c00000b')
            .where1('id', '>', 1)
            .where1('c1', '!=', '123')
            .offset(1)
            .limit(10)
            .order_by('c2')
            .sql())

    conn = await asyncpg.connect('postgres://postgres@localhost:5432')
    '''data = await conn.fetch(info[0], *info[1])
print(info)
print(data)
get_values = lambda x: list(x.values())
print(list(map(get_values, data)))'''



asyncio.get_event_loop().run_until_complete(main())
print('123')

"""