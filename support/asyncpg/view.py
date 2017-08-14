import json

import asyncio
import peewee
from playhouse.postgres_ext import BinaryJSONField
from playhouse.shortcuts import model_to_dict

from mapi.retcode import RETCODE
from mapi.support.asyncpg import query
from mapi.utils import ResourceException
from ...base.view import MView, BaseSQLFunctions

_field_query = '''SELECT a.attname as name, col_description(a.attrelid,a.attnum) as comment,pg_type.typname as typename, a.attnotnull as notnull
  FROM pg_class as c,pg_attribute as a inner join pg_type on pg_type.oid = a.atttypid 
  where c.relname = $1 and a.attrelid = c.oid and a.attnum>0;'''


class BaseModel(peewee.Model):
    def to_dict(self):
        return model_to_dict(self)


class AsyncpgSQLFunctions(BaseSQLFunctions):
    def _get_args(self, args):
        nargs = args
        for i in args:
            field = self.view.fields[i[0]]
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
        return nargs

    def _get_data(self, data):
        ndata = {}
        for k, v in data.items():
            field = self.view.fields[k]
            type_codec = field['typename']

            if type_codec in ['int2', 'int4', 'int8']:
                type_codec = 'int'
                v = int(v)
            elif type_codec in ['float4', 'float8']:
                type_codec = 'float'
                v = float(v)

            ndata[k] = v
        return ndata

    async def select_one(self, si):
        view = self.view
        nargs = self._get_args(si['args'])

        sc = query.SelectCompiler()
        sql = sc.select_raw('*').from_table(view.table_name).simple_where_many(nargs).order_by_many(si['orders']).sql()
        ret = await view.conn.fetchrow(sql[0], *sql[1])

        if ret:
            return RETCODE.SUCCESS, dict(ret)
        else:
            return RETCODE.NOT_FOUND, None

    async def select_count(self, si):
        view = self.view
        nargs = self._get_args(si['args'])

        sc = query.SelectCompiler()
        sql = sc.select_count().from_table(view.table_name).simple_where_many(nargs).order_by_many(si['orders']).sql()
        count = (await view.conn.fetchrow(sql[0], *sql[1]))['count']
        return RETCODE.SUCCESS, count

    async def select_list(self, si, size, offset, *, page=None):
        view = self.view
        nargs = self._get_args(si['args'])

        sc = query.SelectCompiler()
        get_values = lambda x: list(x.values())

        sql = sc.select_raw('*').from_table(view.table_name).simple_where_many(nargs) \
            .order_by_many(si['orders']).limit(size).offset(offset).sql()
        ret = map(get_values, await view.conn.fetch(sql[0], *sql[1]))

        return RETCODE.SUCCESS, list(ret)

    async def update(self, si, data):
        view = self.view
        nargs = self._get_args(si['args'])
        ndata = self._get_data(data)

        uc = query.UpdateCompiler()
        sql = uc.to_table(view.table_name).simple_where_many(nargs).set_values(ndata).sql()
        ret = await view.conn.execute(sql[0], *sql[1]) # ret == "UPDATE X"

        if ret and ret.startswith("UPDATE "):
            num = int(ret[len("UPDATE "):])
            return RETCODE.SUCCESS, {'count': num}
        else:
            return RETCODE.FAILED, None

    async def insert(self, data):
        view = self.view
        ndata = self._get_data(data)
        ic = query.InsertCompiler()
        sql = ic.into_table(view.table_name).set_values(ndata).returning().sql()
        ret = await view.conn.fetchrow(sql[0], *sql[1])
        return RETCODE.SUCCESS, dict(ret)


class AsyncpgMView(MView):
    conn = None
    table_name = None
    sql_cls = AsyncpgSQLFunctions

    @staticmethod
    async def _fetch_fields_by_table_name(conn, table_name):
        info = await conn.fetch(_field_query, table_name)
        if not info:
            raise ResourceException("Table not found: %s" % table_name)
        ret = {}
        for i in info:
            ret[i['name']] = i
        return ret

    @staticmethod
    async def _fetch_fields(cls_or_self):
        if cls_or_self.table_name:
            info = await cls_or_self.conn.fetch(_field_query, cls_or_self.table_name)
            if not info:
                raise ResourceException("Table not found: %s" % cls_or_self.table_name)
            ret = {}
            for i in info:
                ret[i['name']] = i
            cls_or_self.fields = ret
