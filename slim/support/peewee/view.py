import logging
import peewee
from typing import Type, Tuple, List, Iterable, Union

try:
    from playhouse.postgres_ext import JSONField as PG_JSONField, BinaryJSONField as PG_BinaryJSONField, ArrayField as PG_ArrayField
    from playhouse.sqlite_ext import JSONField as SQLITE_JSONField
except ImportError:
    # noinspection PyPep8Naming
    class PG_JSONField: pass

    # noinspection PyPep8Naming
    class PG_BinaryJSONField: pass

    # noinspection PyPep8Naming
    class SQLITE_JSONField: pass

from playhouse.shortcuts import model_to_dict

from ...base.sqlquery import SQL_TYPE, SQLForeignKey, SQL_OP, SQLQueryInfo, SQLQueryOrder, ALL_COLUMNS, \
    SQLValuesToWrite, UpdateInfo, SQL_TYPE_ARRAY
from ...exception import RecordNotFound, AlreadyExists, ResourceException, NotNullConstraintFailed
from ...base.permission import DataRecord, Permissions
from ...utils import to_bin, to_hex, pagination_calc, dict_filter, get_bytes_from_blob
from ...base.view import AbstractSQLView, AbstractSQLFunctions, ViewOptions

logger = logging.getLogger(__name__)


def get_peewee_ver():
    return tuple(map(int, peewee.__version__.split('.')))


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
            elif isinstance(fields[name], peewee.BlobField):
                v = get_bytes_from_blob(v)
            if self.selected != ALL_COLUMNS and (self.selected and (name not in self.selected)):
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
    SQL_OP.NOT_IN: 'not_in',
    SQL_OP.IS: '__rshift__',  # __rshift__ = _e(OP.IS)
    SQL_OP.IS_NOT: '__rshift__',
    SQL_OP.CONTAINS: 'contains'
}


class PeeweeContext:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        db = self.db
        if isinstance(exc_val, peewee.IntegrityError):
            db.rollback()
            if exc_val.args[0].startswith('duplicate key') or '唯一约束' in exc_val.args[0]:
                raise AlreadyExists()
            elif exc_val.args[0].startswith('NOT NULL constraint failed'):
                raise NotNullConstraintFailed()
        elif isinstance(exc_val, peewee.DatabaseError):
            db.rollback()
            logger.error("database error", exc_val)
            raise ResourceException("database error")


# noinspection PyProtectedMember,PyArgumentList
class PeeweeSQLFunctions(AbstractSQLFunctions):
    @property
    def _fields(self):
        return self.vcls._peewee_fields

    @property
    def _model(self):
        return self.vcls.model

    def _build_condition(self, args):
        pw_args = []
        for field_name, op, value in args:
            cond = getattr(self._fields[field_name], _peewee_method_map[op])(value)
            if op == SQL_OP.IS_NOT:
                cond = ~cond
            pw_args.append(cond)
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

    async def select_one(self, info: SQLQueryInfo) -> DataRecord:
        try:
            item = self._make_select(info).get()
            return PeeweeDataRecord(None, item, view=self.vcls)
        except self._model.DoesNotExist:
            raise RecordNotFound(self.vcls.table_name)

    async def select_page(self, info: SQLQueryInfo, size=1, page=1) -> Tuple[Tuple[DataRecord, ...], int]:
        q = self._make_select(info)
        count = q.count()

        # 0.4.2: list api does not return NOT_FOUND anymore
        # if count == 0: raise RecordNotFound(self.vcls.table_name)

        if size == -1:
            page = 1
            size = count

        func = lambda item: PeeweeDataRecord(None, item, view=self.vcls)
        return tuple(map(func, q.paginate(page, size))), count

    def _build_write_condition(self, records: Iterable[DataRecord]):
        records_pk = []
        for record in records:
            records_pk.append(record.get(self.vcls.primary_key))
        pk_field = self.vcls._peewee_fields[self.vcls.primary_key]
        # where pk_field in records_pk
        return pk_field << records_pk

    async def update(self, records: Iterable[DataRecord], values: SQLValuesToWrite, returning=False) -> Union[int, Iterable[DataRecord]]:
        new_vals = {}
        model = self.vcls.model
        db = self.vcls.model._meta.database
        fields = self.vcls._peewee_fields
        cond = self._build_write_condition(records)

        for k, v in values.items():
            if k in fields:
                field = fields[k]

                if isinstance(v, UpdateInfo):
                    if v.op == 'incr': v = field + v.val
                    else: v = v.val

                new_vals[k] = v

        with db.atomic(), PeeweeContext(db):
            if isinstance(db, peewee.PostgresqlDatabase):
                q = model.update(**new_vals).where(cond)
                if returning:
                    # cond: peewee.Expression
                    ret = q.returning(*model._meta.fields.values()).execute()
                    to_record = lambda x: PeeweeDataRecord(None, x, view=self.vcls)
                    items = map(to_record, ret)
                    return list(items)
                else:
                    count = q.execute()
                    return count
            else:
                count = model.update(**new_vals).where(cond).execute()
                if not returning: return count

                to_record = lambda x: PeeweeDataRecord(None, x, view=self.vcls)
                return list(map(to_record, model.select().where(cond).execute()))

    async def insert(self, values_lst: Iterable[SQLValuesToWrite], returning=False) -> Union[int, List[DataRecord]]:
        model = self.vcls.model
        db = model._meta.database

        with db.atomic(), PeeweeContext(db):
            if isinstance(db, peewee.PostgresqlDatabase):
                # 对 postgres 可以直接使用 returning，另外防止一种default的bug
                # https://github.com/coleifer/peewee/issues/1555
                q = model.insert_many(values_lst)
                if returning:
                    ret = q.returning(*model._meta.fields.values()).execute()
                    if get_peewee_ver() >= (3, 8, 2):
                        # incompatible change of peewee: https://github.com/coleifer/peewee/releases/tag/3.8.2
                        to_record = lambda x: PeeweeDataRecord(None, x, view=self.vcls)
                    else:
                        to_record = lambda x: PeeweeDataRecord(None, ret.model(**ret._row_to_dict(x)), view=self.vcls)
                    items = map(to_record, ret)
                    return list(items)
                else:
                    count = q.execute()
                    return count
            else:
                if returning:
                    items = []
                    for values in values_lst:
                        item = model.create(**values)
                        items.append(PeeweeDataRecord(None, item, view=self.vcls))
                    return items
                else:
                    count = model.insert_many(values_lst).execute()
                    return count

    async def delete(self, records: Iterable[DataRecord]):
        cond = self._build_write_condition(records)
        db = self.vcls.model._meta.database

        with db.atomic(), PeeweeContext(db):
            return self.vcls.model.delete().where(cond).execute()


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


def field_class_to_sql_type(field: peewee.Field) -> Union[SQL_TYPE, SQL_TYPE_ARRAY]:
    if isinstance(field, peewee.ForeignKeyField):
        field = field.rel_field

    if isinstance(field, peewee.IntegerField):
        return SQL_TYPE.INT
    elif isinstance(field, peewee.FloatField):
        return SQL_TYPE.FLOAT
    elif isinstance(field, (PG_JSONField, PG_BinaryJSONField, SQLITE_JSONField)):
        # 注意 SQLITE_JSONField 是一个 _StringField 所以要提前
        return SQL_TYPE.JSON
    elif isinstance(field, peewee._StringField):
        return SQL_TYPE.STRING
    elif isinstance(field, peewee.BooleanField):
        return SQL_TYPE.BOOLEAN
    elif isinstance(field, peewee.BlobField):
        return SQL_TYPE.BLOB
    elif isinstance(field, PG_ArrayField):
        field: PG_ArrayField
        return SQL_TYPE_ARRAY(field_class_to_sql_type(field._ArrayField__field))


class PeeweeView(AbstractSQLView):
    is_base_class = True
    _sql_cls = PeeweeSQLFunctions
    options_cls = PeeweeViewOptions
    model = None
    _peewee_fields = {}

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
    async def _fetch_fields(cls_or_self):
        if cls_or_self.model:
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

            cls_or_self.table_name = get_table_name(cls_or_self.model)
            cls_or_self.primary_key = get_pk_name(cls_or_self.model)
            cls_or_self.foreign_keys = {}
            cls_or_self._peewee_fields = {}

            def wrap(name, field) -> str:
                if isinstance(field, peewee.ForeignKeyField):
                    rm = field.rel_model
                    name = '%s_id' % name
                    cls_or_self.foreign_keys[name] = [SQLForeignKey(get_table_name(rm), get_pk_name(rm),
                                                                    field_class_to_sql_type(rm))]

                cls_or_self._peewee_fields[name] = field
                return name

            cls_or_self.fields = {wrap(k, v): field_class_to_sql_type(v) for k, v in cls_or_self.model._meta.fields.items()}

    @staticmethod
    async def permission_valid_check(cls):
        pass
