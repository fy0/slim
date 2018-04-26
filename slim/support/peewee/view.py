import json
import binascii
import logging
from typing import Type, Tuple, List

import peewee
# noinspection PyPackageRequirements
from playhouse.postgres_ext import JSONField as PG_JSONField, BinaryJSONField
from playhouse.sqlite_ext import JSONField as SQLITE_JSONField
from playhouse.shortcuts import model_to_dict

from ...base.sqlquery import SQL_TYPE, SQLForeignKey, SQL_OP, SQLQueryInfo, SQLQueryOrder, ALL_COLUMNS
from ...exception import RecordNotFound
from ...base.permission import DataRecord, Permissions, A
from ...retcode import RETCODE
from ...utils import to_bin, pagination_calc, dict_filter
from ...base.view import AbstractSQLView, AbstractSQLFunctions, ViewOptions

logger = logging.getLogger(__name__)


# noinspection PyProtectedMember
class PeeweeDataRecord(DataRecord):
    def __init__(self, table_name, val: peewee.Model, *, view=None):
        super().__init__(table_name, val)
        self.view = view
        if view:
            # if view exists, get information from View class
            self.table = view.table_name
            self._fields = view.fields
        else:
            self.table = table_name
            self._fields = None
        self.val = val  # 只是为了补全才继承的`

    @property
    def fields(self):
        if not self._fields:
            self._fields = {}
            for name, v in self.val._meta.fields.items():
                if isinstance(v, peewee.ForeignKeyField):
                    name = '%s_id' % name  # foreign key
                self._fields[name] = v
        return self._fields

    def _to_dict(self):
        data = {}
        fields = self.val._meta.fields
        for name, v in model_to_dict(self.val, recurse=False).items():
            if isinstance(fields[name], peewee.ForeignKeyField):
                name = name + '_id'
            if self.selected and (name not in self.selected):
                continue
            data[name] = v

        if self.available_columns != ALL_COLUMNS:
            return dict_filter(data, self.available_columns)

        return data


_peewee_method_map = {
    # '+': '__pos__',
    # '-': '__neg__',
    SQL_OP.EQ: '__eq__',
    SQL_OP.NE: '__ne__',
    SQL_OP.LT: '__lt__',
    SQL_OP.LE: '__le__',
    SQL_OP.GE: '__ge__',
    SQL_OP.GT: '__gt__',
    SQL_OP.IN: '__lshift__',  # __lshift__ = _e(OP.IN)
    SQL_OP.IS: '__rshift__',  # __rshift__ = _e(OP.IS)
    SQL_OP.IS_NOT: '__rshift__',  # __rshift__ = _e(OP.IS)
}


# noinspection PyProtectedMember,PyArgumentList
class PeeweeSQLFunctions(AbstractSQLFunctions):
    @property
    def _fields(self):
        return self.vcls._peewee_field

    @property
    def _model(self):
        return self.vcls.model

    def _build_condition(self, args):
        pw_args = []
        for field_name, op, value in args:
            pw_args.append(getattr(self._fields[field_name], _peewee_method_map[op])(value))
        return pw_args

    def _build_orders(self, orders: List[SQLQueryOrder]):
        ret = []
        for i in orders:
            item = self._fields[i.column]
            if i.order == 'asc':
                item = item.asc()
            elif i.order == 'desc':
                item = item.desc()
            ret.append(item)
        return ret

    def _build_select(self, select: List[str]):
        fields = self._fields
        return [fields[x] for x in select]

    def _make_select(self, info: SQLQueryInfo):
        nargs = self._build_condition(info.conditions)
        orders = self._build_orders(info.orders)
        q = self._model.select(*self._build_select(info.select))

        if nargs: q = q.where(*nargs)  # peewee 不允许 where 时 args 为空
        if orders: q = q.order_by(*orders)
        return q

    async def select(self, info: SQLQueryInfo, size=1, page=1)-> Tuple[Tuple[DataRecord, ...], int]:
        q = self._make_select(info)
        count = q.count()

        if size == -1:
            page = 1
            size = count

        func = lambda item: PeeweeDataRecord(None, item, view=self.vcls)

        try:
            return tuple(map(func, q.paginate(page, size))), count
        except self._model.DoesNotExist:
            raise RecordNotFound()

    async def update(self, info, data):
        nargs = self._get_args(info['conditions'])
        if self.err: return self.err
        if len(nargs) == 0: return RETCODE.SUCCESS, 0

        data = dict_filter(data, self.vcls.fields.keys())
        db = self.vcls.model._meta.database

        kwargs = {}
        for k, v in data.items():
            if k in self.vcls.fields:
                field = self.vcls.fields[k]
                conv_func = conv_func_by_field(field)

                print(k, field, conv_func)
                if conv_func:
                    def foo():
                        if isinstance(v, UpdateInfo):
                            if v.op == 'to':
                                return conv_func(v.val)
                            elif v.op == 'incr':
                                # to_remove.append(k)
                                # to_add.append([field, field + v.val])
                                return field + conv_func(v.val)
                        else:
                            return conv_func(v)

                    code, value = do_conv(foo, RETCODE.INVALID_POSTDATA)
                    if code != RETCODE.SUCCESS:
                        return code, value
                    kwargs[k] = value
                else:
                    if isinstance(v, UpdateInfo):
                        if v.op == 'to':
                            kwargs[k] = v
                        elif v.op == 'incr':
                            kwargs[k] = field + conv_func(v.val)
                    else:
                        kwargs[k] = v

        with db.atomic():
            try:
                count = self.vcls.model.update(**kwargs).where(*nargs).execute()
                return RETCODE.SUCCESS, count
            except peewee.DatabaseError:
                db.rollback()

    async def delete(self, select_info):
        nargs = self._get_args(select_info['conditions'])
        if self.err: return self.err
        count = self.vcls.model.delete().where(*nargs).execute()
        return RETCODE.SUCCESS, count

    async def insert(self, data):
        if not len(data):
            return RETCODE.INVALID_POSTDATA, NotImplemented
        db = self.vcls.model._meta.database

        kwargs = {}
        for k, v in data.items():
            if k in self.vcls.fields:
                field = self.vcls.fields[k]

                conv_func = conv_func_by_field(field)
                if conv_func:
                    foo = lambda: conv_func(v)
                    code, value = do_conv(foo, RETCODE.INVALID_POSTDATA)
                    if code != RETCODE.SUCCESS:
                        return code, value
                    kwargs[k] = value
                else:
                    kwargs[k] = v

        with db.atomic():
            try:
                model = self.vcls.model
                if isinstance(model._meta.database, peewee.PostgresqlDatabase):
                    # 对 postgres 采信于数据库的返回值，防止一种 default 值覆盖
                    # https://github.com/coleifer/peewee/issues/1555
                    ret = model.insert(**kwargs).returning(*model._meta.fields.values()).execute()
                    item = ret.model(**ret._row_to_dict(ret[0]))
                else:
                    item = model.create(**kwargs)
                return RETCODE.SUCCESS, PeeweeDataRecord(None, item, view=self.vcls)
            except peewee.IntegrityError as e:
                if e.args[0].startswith('duplicate key'):
                    return RETCODE.ALREADY_EXISTS, NotImplemented
                else:
                    db.rollback()
                    logger.error("database error", e)
                    return RETCODE.FAILED, NotImplemented
            except peewee.DatabaseError as e:
                db.rollback()
                logger.error("database error", e)
                return RETCODE.FAILED, NotImplemented


class PeeweeViewOptions(ViewOptions):
    def __init__(self, *, list_page_size=20, list_accept_size_from_client=False, permission: Permissions = None,
                 model: peewee.Model = None):
        self.model = model
        super().__init__(list_page_size=list_page_size, list_accept_size_from_client=list_accept_size_from_client,
                         permission=permission)

    def assign(self, obj: Type['PeeweeView']):
        if self.model:
            obj.model = self.model
        super().assign(obj)


def field_class_to_sql_type(field: peewee.Field) -> SQL_TYPE:
    if isinstance(field, peewee.ForeignKeyField):
        field = field.rel_field

    if isinstance(field, peewee.IntegerField):
        return SQL_TYPE.INT
    elif isinstance(field, peewee.FloatField):
        return SQL_TYPE.FLOAT
    elif isinstance(field, peewee._StringField):
        return SQL_TYPE.STRING
    elif isinstance(field, peewee.BooleanField):
        return SQL_TYPE.BOOLEAN
    elif isinstance(field, peewee.BlobField):
        return SQL_TYPE.BLOB
    elif isinstance(field, (PG_JSONField, SQLITE_JSONField)):
        return SQL_TYPE.JSON


class PeeweeView(AbstractSQLView):
    is_base_class = True
    _sql_cls = PeeweeSQLFunctions
    options_cls = PeeweeViewOptions
    model = None
    _peewee_field = {}

    @classmethod
    def cls_init(cls, check_options=True):
        # py3.6: __init_subclass__
        if check_options:
            cls._check_view_options()

        if not cls._is_skip_check():
            if not (cls.__name__ == 'PeeweeView' and AbstractSQLView in cls.__bases__):
                assert cls.model, "%s.model must be specified." % cls.__name__

        AbstractSQLView.cls_init.__func__(cls, False)
        # super().cls_init(False)

    @staticmethod
    async def _fetch_fields(cls):
        if cls.model:
            pv3 = peewee.__version__[0] >= '3'

            # noinspection PyProtectedMember
            def get_pk_name(the_model):
                # http://docs.peewee-orm.com/en/latest/peewee/changes.html#fields
                pk = the_model._meta.primary_key
                return pk.column_name if pv3 else pk.db_column

            # noinspection PyProtectedMember
            def get_table_name(the_model):
                meta = the_model._meta
                return meta.table_name if pv3 else meta.db_table

            cls.table_name = get_table_name(cls.model)
            cls.primary_key = get_pk_name(cls.model)
            cls.foreign_keys = {}

            def wrap(name, field) -> str:
                if isinstance(field, peewee.ForeignKeyField):
                    rm = field.rel_model
                    name = '%s_id' % name
                    cls.foreign_keys[name] = SQLForeignKey(get_table_name(rm), get_pk_name(rm),
                                                           field_class_to_sql_type(rm))

                cls._peewee_field[name] = field
                return name

            cls.fields = {wrap(k, v): field_class_to_sql_type(v) for k, v in cls.model._meta.fields.items()}
