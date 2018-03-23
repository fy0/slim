import json
import binascii
import logging
from typing import Type

import peewee
# noinspection PyPackageRequirements
from playhouse.postgres_ext import BinaryJSONField
from playhouse.shortcuts import model_to_dict

from slim.base.sqlfuncs import UpdateInfo
from ...base.permission import AbilityRecord, Permissions, A
from ...retcode import RETCODE
from ...utils import to_bin, pagination_calc, dict_filter, bool_parse
from ...base.view import AbstractSQLView, AbstractSQLFunctions, ViewOptions

logger = logging.getLogger(__name__)


# noinspection PyProtectedMember
class PeeweeAbilityRecord(AbilityRecord):
    # noinspection PyMissingConstructor
    def __init__(self, table_name, val: peewee.Model, *, view=None, selected=None):
        self.view = view
        self.selected = selected
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

    def keys(self):
        return self.fields.keys()

    def get(self, key):
        return getattr(self.val, key)

    def has(self, key):
        return hasattr(self.val, key)

    def to_dict(self, available_columns=None):
        data = {}
        fields = self.val._meta.fields
        for name, v in model_to_dict(self.val, recurse=False).items():
            if isinstance(fields[name], peewee.ForeignKeyField):
                name = name + '_id'
            if self.selected and (name not in self.selected):
                continue
            data[name] = v

        if available_columns:
            return dict_filter(data, available_columns)

        return data


_peewee_method_map = {
    # '+': '__pos__',
    # '-': '__neg__',
    '=': '__eq__',
    '==': '__eq__',
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
    'in': '__lshift__',  # __lshift__ = _e(OP.IN)
    'is': '__rshift__',  # __rshift__ = _e(OP.IS)
    'isnot': '__rshift__'
}


# noinspection PyProtectedMember,PyArgumentList
class PeeweeSQLFunctions(AbstractSQLFunctions):
    def _get_args(self, args):
        pw_args = []
        for field_name, op, value in args:
            field = self.vcls.fields[field_name]
            if isinstance(field, peewee.ForeignKeyField):
                tfield = field.to_field
            else:
                tfield = field

            conv_func = None
            # 说明：我记得 peewee 会自动完成 int/float 的转换，所以不用自己转
            if isinstance(tfield, peewee.BlobField):
                def conv_func(val):
                    if isinstance(val, memoryview):
                        return val
                    # FIX: 其实这可能有点问题，因为None是一个合法的值
                    if val is None:
                        return val
                    # 同样的，NotImplemented 似乎可能是一个非法值
                    # 很有可能不存在一部分是 NotImplemented 另一部分不是的情况
                    if val is NotImplemented:
                        return
                    return to_bin(val)
            elif isinstance(tfield, peewee.BooleanField):
                conv_func = bool_parse

            if conv_func:
                try:
                    if op == 'in':
                        value = list(map(conv_func, value))
                    else:
                        value = conv_func(value)
                except binascii.Error:
                    self.err = RETCODE.INVALID_PARAMS, 'Invalid query value for blob: Odd-length string'
                    return
                except ValueError as e:
                    self.err = RETCODE.INVALID_PARAMS, ' '.join(map(str, e.args))

            pw_args.append(getattr(field, _peewee_method_map[op])(value))
        return pw_args

    def _get_orders(self, orders):
        # 注：此时早已经过检查可确认orders中的列存在
        ret = []
        fields = self.vcls.fields

        for i in orders:
            if len(i) == 2:
                # column, order
                item = fields[i[0]]
                if i[1] == 'asc': item = item.asc()
                elif i[1] == 'desc': item = item.desc()
                ret.append(item)

            elif len(i) == 3:
                # column, order, table
                # TODO: 日后再说
                pass
        return ret

    def _make_select(self, info):
        nargs = self._get_args(info['conditions'])
        if self.err: return
        orders = self._get_orders(info['orders'])
        if self.err: return

        q = self.vcls.model.select(*[self.vcls.fields[x] for x in info['select']])
        # peewee 不允许 where 时 args 为空
        if nargs: q = q.where(*nargs)
        if orders: q = q.order_by(*orders)
        return q

    async def select_one(self, info):
        try:
            q = self._make_select(info)
            if self.err: return self.err
            return RETCODE.SUCCESS, PeeweeAbilityRecord(None, q.get(), view=self.vcls, selected=info['select'])
        except self.vcls.model.DoesNotExist:
            return RETCODE.NOT_FOUND, NotImplemented

    async def select_paginated_list(self, info, size, page):
        q = self._make_select(info)
        if self.err: return self.err
        count = q.count()
        pg = pagination_calc(count, size, page)
        if size == -1: size = count or 20  # get all, care about crash when count == 0

        func = lambda item: PeeweeAbilityRecord(None, item, view=self.vcls, selected=info['select'])
        pg["items"] = list(map(func, q.paginate(page, size)))
        return RETCODE.SUCCESS, pg

    async def update(self, info, data):
        nargs = self._get_args(info['conditions'])
        if self.err: return self.err
        if len(nargs) == 0: return RETCODE.SUCCESS, 0

        data = dict_filter(data, self.vcls.fields.keys())
        db = self.vcls.model._meta.database

        with db.atomic():
            try:
                for k, v in data.items():
                    if isinstance(v, UpdateInfo):
                        if v.op == 'to':
                            data[k] = v.val
                        elif v.op == 'incr':
                            field = self.vcls.fields[k]
                            #to_remove.append(k)
                            #to_add.append([field, field + v.val])
                            data[k] = field + v.val

                count = self.vcls.model.update(**data).where(*nargs).execute()
                return RETCODE.SUCCESS, count
            except peewee.DatabaseError:
                db.rollback()

    def delete(self, select_info):
        nargs = self._get_args(select_info['conditions'])
        if self.err: return self.err
        count = self.vcls.model.delete().where(*nargs).execute()
        return RETCODE.SUCCESS, count

    async def insert(self, data):
        if not len(data):
            return RETCODE.INVALID_PARAMS, NotImplemented
        db = self.vcls.model._meta.database

        kwargs = {}
        for k, v in data.items():
            if k in self.vcls.fields:
                field = self.vcls.fields[k]
                if isinstance(field, BinaryJSONField):
                    kwargs[k] = json.loads(v)
                else:
                    kwargs[k] = v

        with db.atomic():
            try:
                item = self.vcls.model.create(**kwargs)
                return RETCODE.SUCCESS, PeeweeAbilityRecord(None, item, view=self.vcls)
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


class PeeweeView(AbstractSQLView):
    is_base_class = True
    _sql_cls = PeeweeSQLFunctions
    options_cls = PeeweeViewOptions

    model = None

    # fields
    # table_name
    # primary_key
    # foreign_keys

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

    # noinspection PyProtectedMember
    @staticmethod
    async def _fetch_fields(cls_or_self):
        if cls_or_self.model:
            pv3 = peewee.__version__[0] == '3'
            model = cls_or_self.model
            if pv3:
                # peewee 3.X
                # http://docs.peewee-orm.com/en/latest/peewee/changes.html#fields
                cls_or_self.primary_key = model._meta.primary_key.column_name
            else:
                # peewee 2.X
                cls_or_self.primary_key = model._meta.primary_key.db_column
            cls_or_self.foreign_keys = {}

            def wrap(name, field):
                if isinstance(field, peewee.ForeignKeyField):
                    name = '%s_id' % name
                    cls_or_self.foreign_keys[name] = [field.rel_model._meta.db_table]
                return name

            cls_or_self.fields = {wrap(k, v): v for k, v in model._meta.fields.items()}
            if pv3:
                cls_or_self.table_name = model._meta.table_name
            else:
                cls_or_self.table_name = model._meta.db_table
