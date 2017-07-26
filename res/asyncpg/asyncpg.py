import json
import asyncio

from mapi.res.asyncpg.query import parse_query_by_json, QueryException
from . import query
from mapi.resource import Resource
from mapi.retcode import RETCODE
from mapi.utils import pagination_calc, ResourceException


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


class AsyncpgResource(Resource):
    surface = Resource.surface.copy()
    surface['exlist'] = Resource._surface_list_tmpl('exlist')

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

    def _query_order(self, text):
        orders = []
        for i in text.split(','):
            table = None
            items = i.split('.', 2)

            if len(items) == 1: continue
            elif len(items) == 2: column, order = items
            else: column, order, table = items

            order = order.lower()
            if column not in self.fields:
                raise ResourceException('Column not found: %s' % column)
            if order not in ('asc', 'desc'):
                raise ResourceException('Invalid order column: %s' % order)


            orders.append([column, order, table])
        return orders

    def _query_extra(self, text):
        ''' 这部分思路有问题，过于繁琐，且不应该提供跨表查询能力
        extra = json.loads(text)
        new_extra = {
            'groups': {}
        }
        for name, group in extra['groups']:
            """
            # name '_root' reserved
            group = {
                'table': '{table_name}',
                'logic_op': '{and, or}',
                'children': {...}
            }
           """
            new_group = {}
            new_group['table'] = group['table']
            if new_group['logic_op'].lower() not in ('and', 'or'):
                raise ResourceException('Invalid logic operator: %s' % new_group['logic_op'])
            new_group['logic_op'] = new_group['logic_op'].lower()
            new_extra['groups'][name] = new_group
        return new_extra'''
        extra = json.loads(text)
        pass

    def _query_convert(self, params):
        args = []
        orders = []
        extra = None

        for k, v in params.items():
            group = None
            # @ ...
            info = k.rsplit('@', 1)
            if len(info) == 2:
                group = info[1].split('.')
                k = info[0]
            # xxx.{op}@ ...
            info = k.split('.', 1)

            if len(info) < 1:
                raise ResourceException('Invalid request parameter')

            field_name = info[0]
            if field_name == 'order':
                orders = self._query_order(v)
                continue
            elif field_name == '_ext':
                extra = self._query_extra(v)
                continue
            op = '='

            if field_name not in self.fields:
                raise ResourceException('Column not found: %s' % field_name)
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

            args.append([field_name, op, v, type_codec, group])
        return args, orders, extra

    async def get(self, request):
        sc = query.SelectCompiler()
        args, orders, extra = self._query_convert(request.query)
        sql = sc.select_raw('*').from_table(self.table_name).simple_where_many(args).set_ext(extra).order_by_many(orders).sql()
        ret = await self.conn.fetchrow(sql[0], *sql[1])

        if ret:
            self.finish(RETCODE.SUCCESS, json.dumps(list(ret.values())))
        else:
            self.finish(RETCODE.NOT_FOUND)

    async def set(self, request):
        uc = query.UpdateCompiler()
        args, orders, extra = self._query_convert(request.query)
        sql = uc.to_table(self.table_name).set_values()
        sql = sc.select_raw('*').from_table(self.table_name).simple_where_many(args).set_ext(extra).order_by_many(orders).sql()

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

        sc = query.SelectCompiler()
        args, orders, extra = self._query_convert(request.query)
        sql = sc.select_count().from_table(self.table_name).simple_where_many(args).set_ext(extra).order_by_many(orders).sql()
        count = await self.conn.fetchval(sql[0], *sql[1])

        pg = pagination_calc(count, size, page)
        get_values = lambda x: list(x.values())

        sc.reset()
        sql = sc.select_raw('*').from_table(self.table_name).simple_where_many(args).set_ext(extra) \
            .order_by_many(orders).limit(size).offset(size * (page-1)).sql()
        ret = map(get_values, await self.conn.fetch(sql[0], *sql[1]))
        pg["items"] = list(ret)
        self.finish(RETCODE.SUCCESS, pg)

    async def exlist(self, request):
        page = request.match_info.get('page', '1')
        size = request.match_info.get('size', None)
        query_json = request.query.get('query', None)

        if not page.isdigit():
            return self.finish(RETCODE.INVALID_PARAMS)

        if size and not size.isdigit():
            return self.finish(RETCODE.INVALID_PARAMS)

        if not query_json:
            return self.finish(RETCODE.INVALID_PARAMS)

        page = int(page)
        size = int(size or self.LIST_PAGE_SIZE)

        sc = query.SelectCompiler()
        try:
            info = parse_query_by_json(query_json)
            sql = sc.select_count().from_tables(info['tables']).where(*info['wheres']).sql()
            count = await self.conn.fetchval(sql[0], *sql[1])

            pg = pagination_calc(count, size, page)
            get_values = lambda x: list(x.values())

            sc.reset()
            sql = sc.select(*info['columns']).from_tables(info['tables']).where(*info['wheres']) \
                .limit(size).offset(size * (page - 1)).sql()

            ret = map(get_values, await self.conn.fetch(sql[0], *sql[1]))
            pg["items"] = list(ret)
            self.finish(RETCODE.SUCCESS, pg)
        except QueryException as e:
            self.finish(RETCODE.INVALID_PARAMS, e.args[0])


"""
sc = QueryCompiler.SelectCompiler()
print(sc.select_count().from_table('T596718ed293b327c5c00000b').sql())
print(sc.select_raw('*').from_table('T596718ed293b327c5c00000b')
      .simple_where_one('id', '=', 1)
      .simple_where_one('c1', '!=', '123')
      .offset(1)
      .limit(10)
      .order_by('c2')
      .sql())


async def main():
    sc = QueryCompiler.SelectCompiler()
    info = (sc.select_raw('*').from_table('T596718ed293b327c5c00000b')
            .simple_where_one('id', '>', 1)
            .simple_where_one('c1', '!=', '123')
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
