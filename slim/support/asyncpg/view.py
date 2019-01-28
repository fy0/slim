import binascii
from asyncpg import Record, Type

from ...base.permission import A, DataRecord, Permissions
from ...retcode import RETCODE
from ...support.asyncpg import query
from ...utils import to_bin, pagination_calc, dict_filter, bool_parse
from ...exception import SyntaxException
from ...base.view import AbstractSQLView, AbstractSQLFunctions, ViewOptions

# noinspection SqlDialectInspection,SqlNoDataSourceInspection
_field_query = '''SELECT a.attname as name, col_description(a.attrelid,a.attnum) as comment,
  pg_type.typname as typename, a.attnotnull as notnull
  FROM pg_class as c,pg_attribute as a inner join pg_type on pg_type.oid = a.atttypid 
  where c.relname = $1 and a.attrelid = c.oid and a.attnum>0;'''

_fk_query = '''
SELECT a.attname, c2.relname
  FROM pg_class as c, pg_class as c2, pg_attribute as a,
    pg_CONSTRAINT as con
  WHERE c.oid = con.conrelid -- OID与表关联
        and c.relname = $1 -- 查询当前表的OID
        and con.confrelid = c2.oid -- 查询出关联的表名
        and a.attrelid = c.oid -- 找到对应表的列的属性
        and a.attnum=ANY(con.conkey); -- 外键位置与具体列对应
'''

class AsyncpgDataRecord(DataRecord):
    # noinspection PyMissingConstructor
    def __init__(self, table_name, val: Record):
        self.table = table_name
        self.val = val  # 只是为了补全

    def keys(self):
        return self.val.keys()

    def get(self, key):
        return self.val['key']

    def has(self, key):
        return key in self.val

    def to_dict(self, available_columns=None):
        if available_columns:
            return dict_filter(self.val, available_columns)
        return dict(self.val)


class AsyncpgSQLFunctions(AbstractSQLFunctions):
    def _get_args(self, args):
        nargs = []
        # 这里注意，args可能多次使用，不要修改其中内容
        for i in args:
            i = i[:]
            field = self.vcls.fields[i[0]]
            type_codec = field['typename']

            # https://www.postgresql.org/docs/9.6/static/datatype.html
            # asyncpg/protocol/protocol.pyx
            # import asyncpg.protocol.protocol
            conv_func = None
            if type_codec in ['int2', 'int4', 'int8']:
                type_codec = 'int'
                conv_func = int
            elif type_codec in ['float4', 'float8']:
                type_codec = 'float'
                conv_func = float
            elif type_codec == 'bytea':
                conv_func = to_bin
            elif type_codec == 'bool':
                conv_func = bool_parse

            if conv_func:
                try:
                    if i[1] == 'in':
                        i[2] = list(map(conv_func, i[2]))
                    else:
                        i[2] = conv_func(i[2])
                except binascii.Error:
                    self.err = RETCODE.INVALID_PARAMS, 'Invalid query value for blob: Odd-length string'
                    return
                except ValueError as e:
                    self.err = RETCODE.INVALID_PARAMS, ' '.join(map(str, e.args))

            nargs.append([*i, type_codec])
        return nargs

    def _get_data(self, data):
        ndata = {}
        for k, v in data.items():
            field = self.vcls.fields[k]
            type_codec = field['typename']

            if type_codec in ['int2', 'int4', 'int8']:
                # type_codec = 'int'
                v = int(v)
            elif type_codec in ['float4', 'float8']:
                # type_codec = 'float'
                v = float(v)
            elif type_codec == 'bytea':
                # type_codec = 'bytea'
                v = to_bin(v)

            ndata[k] = v
        return ndata

    async def select_one(self, info):
        view = self.vcls
        nargs = self._get_args(info['conditions'])
        if self.err: return self.err

        sc = query.SelectCompiler()
        sql = sc.select(info['select']).from_table(view.table_name).simple_where_many(nargs)\
            .order_by_many(info['orders']).sql()
        ret = await view.conn.fetchrow(sql[0], *sql[1])
        if not ret: return RETCODE.NOT_FOUND, NotImplemented

        if ret:
            return RETCODE.SUCCESS, AsyncpgDataRecord(view.table_name, ret)
        else:
            return RETCODE.NOT_FOUND, NotImplemented

    async def select_paginated_list(self, info, size, page):
        nargs = self._get_args(info['conditions'])
        if self.err: return self.err

        sc = query.SelectCompiler()
        sql = sc.select_count().from_table(self.vcls.table_name).simple_where_many(nargs)\
            .order_by_many(info['orders']).sql()
        count = (await self.vcls.conn.fetchrow(sql[0], *sql[1]))['count']

        pg = pagination_calc(count, size, page)
        if size == -1: size = count  # get all
        offset = size * (page - 1)

        sc.reset()
        sql = sc.select(info['select']).from_table(self.vcls.table_name).simple_where_many(nargs) \
            .order_by_many(info['orders']).limit(size).offset(offset).sql()
        ret = await self.vcls.conn.fetch(sql[0], *sql[1])
        func = lambda item: AsyncpgDataRecord(self.vcls.table_name, item)
        pg["items"] = list(map(func, ret))
        return RETCODE.SUCCESS, pg

    async def update(self, info, data):
        view = self.vcls
        nargs = self._get_args(info['conditions'])
        if self.err: return self.err

        columns = view.ability.can_with_columns(None, A.WRITE, view.table_name, data.keys())
        if not columns:
            return RETCODE.PERMISSION_DENIED, NotImplemented
        ndata = self._get_data(dict_filter(data, columns))

        uc = query.UpdateCompiler()
        sql = uc.to_table(view.table_name).simple_where_many(nargs).set_values(ndata).sql()
        ret = await view.conn.execute(sql[0], *sql[1])  # ret == "UPDATE X"

        if ret and ret.startswith("UPDATE "):
            num = int(ret[len("UPDATE "):])
            return RETCODE.SUCCESS, {'count': num}
        else:
            return RETCODE.FAILED, NotImplemented

    async def insert(self, data):
        ndata = self._get_data(data)
        ic = query.InsertCompiler()
        sql = ic.into_table(self.vcls.table_name).set_values(ndata).returning().sql()
        ret = await self.vcls.conn.fetchrow(sql[0], *sql[1])
        return RETCODE.SUCCESS, AsyncpgDataRecord(self.vcls.table_name, ret)


class AsyncpgViewOptions(ViewOptions):
    def __init__(self, *, list_page_size=20, list_accept_size_from_client=False, permission: Permissions = None,
                 conn=None, table_name: str=None):
        self.conn = conn
        self.table_name = table_name
        super().__init__(list_page_size=list_page_size, list_accept_size_from_client=list_accept_size_from_client,
                         permission=permission)

    def assign(self, obj: Type['AsyncpgView']):
        if self.conn:
            obj.conn = self.conn
        if self.table_name:
            obj.table_name = self.table_name
        super().assign(obj)


class AsyncpgView(AbstractSQLView):
    is_base_class = True
    options_cls = AsyncpgViewOptions
    conn = None
    table_name = None

    @classmethod
    def cls_init(cls, check_options=True):
        # py3.6: __init_subclass__

        skip_check = False
        if 'is_base_class' in cls.__dict__:
            skip_check = getattr(cls, 'is_base_class')

        if skip_check:
            if not (cls.__name__ == 'AsyncpgView' and AbstractSQLView in cls.__bases__):
                assert cls.conn, "%s.conn must be specified." % cls.__name__
                assert cls.table_name, "%s.conn must be specified." % cls.__name__

        AbstractSQLView.cls_init.__func__(cls, False)
        # super().cls_init(False)

    @staticmethod
    async def _fetch_fields(cls_or_self):
        if cls_or_self.table_name:
            info = await cls_or_self.conn.fetch(_field_query, cls_or_self.table_name)
            if not info:
                raise SyntaxException("Table not found: %s" % cls_or_self.table_name)
            ret = {}
            for i in info:
                ret[i['name']] = i
            cls_or_self.fields = ret

            info = await cls_or_self.conn.fetch(_fk_query, cls_or_self.table_name)
            for i in info:
                ret[i['attname']] = [i['relname']]
            cls_or_self.foreign_keys = ret

    @staticmethod
    async def permission_valid_check(cls):
        pass
