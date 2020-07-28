import logging
import peewee

from typing import List, Tuple, Iterable, Union
from playhouse.postgres_ext import ArrayField, SQL

from slim.support.peewee.data_record import PeeweeDataRecord
from slim.utils import sentinel
from ...base.sqlquery import SQL_OP, SQLQueryOrder, SQLQueryInfo, DataRecord, SQLValuesToWrite
from ...base.sqlfuncs import AbstractSQLFunctions

from ...exception import RecordNotFound, AlreadyExists, ResourceException, NotNullConstraintFailed

logger = logging.getLogger(__name__)


def get_peewee_ver():
    return tuple(map(int, peewee.__version__.split('.')))


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
    SQL_OP.CONTAINS: 'contains',
    SQL_OP.CONTAINS_ANY: 'contains_any',
    SQL_OP.PREFIX: 'startswith',

    SQL_OP.LIKE: '__mod__',
    SQL_OP.ILIKE: '__pow__'
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
            assert self._fields.get(field_name), 'Column name in condition not found: %r' % field_name
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
        db = self.vcls.model._meta.database
        with PeeweeContext(db):
            try:
                item = self._make_select(info).get()
                return PeeweeDataRecord(None, item, view=self.vcls)
            except self._model.DoesNotExist:
                raise RecordNotFound(self.vcls.table_name)

    async def select_page(self, info: SQLQueryInfo, page=1, size=1) -> Tuple[Tuple[DataRecord, ...], int]:
        q = self._make_select(info)
        db = self.vcls.model._meta.database

        # select may cause transaction aborted
        # for example: select * from xx where id in ()
        with PeeweeContext(db):
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
                is_array_field = isinstance(field, ArrayField)

                if is_array_field:
                    if k in values.set_add_fields:
                        # 这里需要加 [v] 的原因是，params需要数组，举例来说为，[v1,v2,v3]
                        # v = SQL('%s || %%s' % field.column_name, [v])
                        v = SQL('(select ARRAY((select unnest(%s)) union (select unnest(%%s))))' % field.column_name, [v])

                    if k in values.set_remove_fields:
                        v = SQL('(select ARRAY((select unnest(%s)) except (select unnest(%%s))))' % field.column_name, [v])

                    # 尚未启用
                    # if k in values.array_append:
                    #     v = SQL('array_append(%s, %%s)' % field.column_name, [v])

                    # if k in values.array_remove:
                    #     v = SQL('array_remove(%s, %%s)' % field.column_name, [v])

                else:
                    if k in values.incr_fields:
                        v = field + v
                    if k in values.decr_fields:
                        v = field - v

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

    async def insert(self, values_lst: Iterable[SQLValuesToWrite], returning=False, ignore_exists=False) -> Union[int, List[DataRecord]]:
        # 基本上，单条插入时，不忽略重复，多条时忽略
        model = self.vcls.model
        db = model._meta.database

        with db.atomic(), PeeweeContext(db):
            if isinstance(db, peewee.PostgresqlDatabase):
                # 对 postgres 可以直接使用 returning，另外防止一种default的bug
                # https://github.com/coleifer/peewee/issues/1555
                q = model.insert_many(values_lst)
                if ignore_exists:
                    q = q.on_conflict_ignore()
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
                        try:
                            item = model.create(**values)
                            items.append(PeeweeDataRecord(None, item, view=self.vcls))
                        except peewee.IntegrityError as e:
                            db.rollback()
                            if not ignore_exists:
                                raise e
                    return items
                else:
                    q = model.insert_many(values_lst)
                    if ignore_exists:
                        q = q.on_conflict_ignore()
                    count = q.execute()
                    return count

    async def delete(self, records: Iterable[DataRecord]):
        cond = self._build_write_condition(records)
        db = self.vcls.model._meta.database

        with db.atomic(), PeeweeContext(db):
            return self.vcls.model.delete().where(cond).execute()
