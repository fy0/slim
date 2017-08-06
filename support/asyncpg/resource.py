import asyncio
import json

from mapi.retcode import RETCODE
from mapi.support.asyncpg import query
from mapi.support.asyncpg.query import parse_query_by_json, QueryException, InsertCompiler
from ...base.resource import Resource, QueryResource
from ...utils import pagination_calc, ResourceException


class AsyncpgResource(QueryResource):
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
            if not info:
                raise ResourceException("Table not found: %s" % self.table_name)
            ret = {}
            for i in info:
                ret[i['name']] = i
            self.fields = ret
            return ret

    def _query_convert(self, params):
        args, orders, ext = super()._query_convert(params)
        for i in args:
            field = self.fields[i[0]]
            type_codec = field['typename']

            # https://www.postgresql.org/docs/9.6/static/datatype.html
            # asyncpg/protocol/protocol.pyx
            if type_codec in ['int2', 'int4', 'int8']:
                type_codec = 'int'
                i[2] = int(i[2])
            elif type_codec in ['float4', 'float8']:
                type_codec = 'float'
                i[2] = float(i[2])

            i.append(type_codec)
        return args, orders, ext

    async def get(self, request):
        args, orders, ext = self._query_convert(request.query)
        fails, columns_for_read = self.permission.check_select(self, request, args, orders, ext)
        if fails: return self.fields(RETCODE.PERMISSION_DENIED, json.dumps(fails))

        sc = query.SelectCompiler()
        sql = sc.select_raw('*').from_table(self.table_name).simple_where_many(args).order_by_many(orders).sql()
        ret = await self.conn.fetchrow(sql[0], *sql[1])

        if ret:
            self.finish(RETCODE.SUCCESS, json.dumps(list(ret.values())))
        else:
            self.finish(RETCODE.NOT_FOUND)

    async def set(self, request):
        args, orders, ext = self._query_convert(request.query)
        fails, columns_for_read = self.permission.check_select(self, request, args, orders, ext)
        if fails: return self.finish(RETCODE.PERMISSION_DENIED, fails)

        data = await request.post()
        uc = query.UpdateCompiler()
        sql = uc.to_table(self.table_name).simple_where_many(args).set_values(data).sql()
        ret = await self.conn.execute(sql[0], *sql[1]) # ret == "UPDATE X"

        if ret and ret.startswith("UPDATE "):
            num = int(ret[len("UPDATE "):])
            return self.finish(RETCODE.SUCCESS, {'count': num})
        else:
            return self.finish(RETCODE.FAILED)

    async def new(self, request):
        ic = InsertCompiler()
        ic.set_values()

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
        page, size = self._get_list_page_and_size(request)
        args, orders, ext = self._query_convert(request.query)
        fails, columns_for_read = self.permission.check_select(self, request, args, orders, ext)
        if fails: return self.fields(RETCODE.PERMISSION_DENIED, json.dumps(fails))

        sc = query.SelectCompiler()
        sql = sc.select_count().from_table(self.table_name).simple_where_many(args).order_by_many(orders).sql()
        count = await self.conn.fetchval(sql[0], *sql[1])

        pg = pagination_calc(count, size, page)
        get_values = lambda x: list(x.values())

        sc.reset()
        sql = sc.select_raw('*').from_table(self.table_name).simple_where_many(args) \
            .order_by_many(orders).limit(size).offset(size * (page-1)).sql()
        ret = map(get_values, await self.conn.fetch(sql[0], *sql[1]))
        pg["items"] = list(ret)
        self.finish(RETCODE.SUCCESS, pg)

    async def exlist(self, request):
        page, size = self._get_list_page_and_size(request)
        query_json = request.query.get('query', None)

        if not query_json:
            return self.finish(RETCODE.INVALID_PARAMS)

        sc = query.SelectCompiler()
        try:
            info = parse_query_by_json(query_json)
            sql = sc.select_count().from_tables(info['tables']).where(info['wheres']).sql()
            count = await self.conn.fetchval(sql[0], *sql[1])

            pg = pagination_calc(count, size, page)
            get_values = lambda x: list(x.values())

            sc.reset()
            sql = sc.select(*info['columns']).from_tables(info['tables']).where(info['wheres']) \
                .limit(size).offset(size * (page - 1)).sql()
            print(sql)

            ret = map(get_values, await self.conn.fetch(sql[0], *sql[1]))
            pg["items"] = list(ret)
            self.finish(RETCODE.SUCCESS, pg)
        except QueryException as e:
            self.finish(RETCODE.INVALID_PARAMS, e.args[0])
