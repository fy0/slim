import json
import binascii
import logging
from typing import Type

import peewee
# noinspection PyPackageRequirements
from playhouse.postgres_ext import BinaryJSONField
from playhouse.shortcuts import model_to_dict

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
            field = self.view.fields[field_name]
            if isinstance(field, peewee.ForeignKeyField):
                tfield = field.to_field
            else:
                tfield = field

            conv_func = None
            # 说明：我记得 peewee 会自动完成 int/float 的转换，所以不用自己转
            if isinstance(tfield, peewee.BlobField):
                conv_func = to_bin
            elif isinstance(tfield, peewee.BooleanField):
                conv_func = bool_parse

            if conv_func:
                try:
                    if op == 'in':
                        value = list(map(conv_func, value))
                    else:
                        value = conv_func(value)
                except binascii.Error:
                    self.err = RETCODE.INVALID_HTTP_PARAMS, 'Invalid query value for blob: Odd-length string'
                    return
                except ValueError as e:
                    self.err = RETCODE.INVALID_HTTP_PARAMS, ' '.join(map(str, e.args))

            pw_args.append(getattr(field, _peewee_method_map[op])(value))
        return pw_args

    def _get_orders(self, orders):
        # 注：此时早已经过检查可确认orders中的列存在
        ret = []
        fields = self.view.fields

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
        nargs = self._get_args(info['args'])
        if self.err: return
        orders = self._get_orders(info['orders'])
        if self.err: return

        q = self.view.model.select(*[self.view.fields[x] for x in info['select']])
        # peewee 不允许 where 时 args 为空
        if nargs: q = q.where(*nargs)
        if orders: q = q.order_by(*orders)
        return q

    async def select_one(self, info):
        try:
            q = self._make_select(info)
            if self.err: return self.err
            return RETCODE.SUCCESS, PeeweeAbilityRecord(None, q.get(), view=self.view, selected=info['select'])
        except self.view.model.DoesNotExist:
            return RETCODE.NOT_FOUND, None

    async def select_paginated_list(self, info, size, page):
        q = self._make_select(info)
        count = q.count()
        pg = pagination_calc(count, size, page)
        if size == -1: size = count  # get all

        func = lambda item: PeeweeAbilityRecord(None, item, view=self.view, selected=info['select'])
        pg["items"] = list(map(func, q.paginate(page, size)))
        return RETCODE.SUCCESS, pg

    async def update(self, info, data):
        try:
            q = self._make_select(info)
            if self.err: return self.err
            item = q.get()
            db = self.view.model._meta.database
            with db.atomic():
                ok = False
                try:
                    for k, v in data.items():
                        if k in self.view.fields:
                            setattr(item, k, v)
                    item.save()
                    ok = True
                except peewee.DatabaseError:
                    db.rollback()

            if ok:
                return RETCODE.SUCCESS, {'count': 1}

        except self.view.model.DoesNotExist:
            return RETCODE.NOT_FOUND, None

    async def insert(self, data):
        if not len(data):
            return RETCODE.INVALID_HTTP_PARAMS, None
        db = self.view.model._meta.database

        kwargs = {}
        for k, v in data.items():
            if k in self.view.fields:
                field = self.view.fields[k]
                if isinstance(field, BinaryJSONField):
                    kwargs[k] = json.loads(v)
                else:
                    kwargs[k] = v

        with db.atomic():
            try:
                item = self.view.model.create(**kwargs)
                return RETCODE.SUCCESS, PeeweeAbilityRecord(None, item, view=self.view)
            except peewee.DatabaseError as e:
                db.rollback()
                logger.error("database error", e)
                return RETCODE.FAILED, None


class PeeweeViewOptions(ViewOptions):
    def __init__(self, *, list_page_size=20, list_accept_size_from_client=False, permission: Permissions = None,
                 model:peewee.Model=None):
        self.model = model
        super().__init__(list_page_size=list_page_size, list_accept_size_from_client=list_accept_size_from_client,
                         permission=permission)

    def assign(self, obj: Type['PeeweeView']):
        if self.model:
            obj.model = self.model
        super().assign(obj)


class PeeweeView(AbstractSQLView):
    options_cls = PeeweeViewOptions
    model = None
    # fields
    # table_name

    @classmethod
    def cls_init(cls, check_options=True):
        # py3.6: __init_subclass__
        if check_options:
            cls._check_view_options()
        if not (cls.__name__ == 'PeeweeView' and AbstractSQLView in cls.__bases__):
            assert cls.model, "%s.model must be specified." % cls.__name__
        super().cls_init(False)

    def __init__(self, request):
        super().__init__(request)
        self._sql = PeeweeSQLFunctions(self)

    # noinspection PyProtectedMember
    @staticmethod
    async def _fetch_fields(cls_or_self):
        if cls_or_self.model:
            def wrap(name, field):
                if isinstance(field, peewee.ForeignKeyField):
                    return '%s_id' % name
                return name
            cls_or_self.fields = {wrap(k, v): v for k, v in cls_or_self.model._meta.fields.items()}
            cls_or_self.table_name = cls_or_self.model._meta.db_table
