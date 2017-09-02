import json
import binascii
import peewee
from playhouse.postgres_ext import BinaryJSONField
from playhouse.shortcuts import model_to_dict

from ...base.permission import AbilityRecord
from ...retcode import RETCODE
from ...utils import to_bin, pagination_calc, dict_filter
from ...base.view import View, BaseSQLFunctions


class PeeweeAbilityRecord(AbilityRecord):
    # noinspection PyMissingConstructor
    def __init__(self, table_name, val: peewee.Model):
        self.table = table_name
        self.val = val  # 只是为了补全才继承的

    def keys(self):
        # noinspection PyProtectedMember
        return self.val._meta.fields.keys()

    def get(self, key):
        return getattr(self.val, key)

    def has(self, key):
        return hasattr(self.val, key)

    def to_dict(self, available_columns=None):
        if available_columns:
            return dict_filter(model_to_dict(self.val), available_columns)
        return model_to_dict(self.val)


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
class PeeweeSQLFunctions(BaseSQLFunctions):
    def _get_args(self, args):
        pw_args = []
        for field_name, op, value in args:
            field = self.view.fields[field_name]

            if isinstance(field, peewee.BlobField):
                try:
                    if op == 'in':
                        value = list(map(to_bin, value))
                    else:
                        value = to_bin(value)
                except binascii.Error:
                    self.err = RETCODE.INVALID_PARAMS, 'Invalid query value for blob: Odd-length string'
                    return

            pw_args.append(getattr(field, _peewee_method_map[op])(value))
        return pw_args

    async def select_one(self, info):
        nargs = self._get_args(info['args'])
        if self.err: return self.err
        try:
            item = self.view.model.get(*nargs)
            return RETCODE.SUCCESS, PeeweeAbilityRecord(self.view.table_name, item)
        except self.view.model.DoesNotExist:
            return RETCODE.NOT_FOUND, None

    async def select_pagination_list(self, info, size, page):
        nargs = self._get_args(info['args'])
        if self.err: return self.err
        q = self.view.model.select().where(*nargs) if nargs else self.view.model.select()

        count = q.count()
        pg = pagination_calc(count, size, page)
        # offset = size * (page - 1)

        func = lambda item: PeeweeAbilityRecord(self.view.table_name, item)
        pg["items"] = list(map(func, q.paginate(page, size)))
        return RETCODE.SUCCESS, pg

    async def update(self, info, data):
        pw_args = self._get_args(info['args'])
        if self.err: return self.err

        try:
            # noinspection PyArgumentList
            item = self.view.model.get(*pw_args)
            db = self.view.model._meta.database
            with db.atomic():
                ok = False
                try:
                    for k, v in data.items():
                        if k in self.view.fields:
                            setattr(item, k, v)
                    item.save()
                    ok = True
                except self.view.model.ErrorSavingData:
                    db.rollback()

            if ok:
                return RETCODE.SUCCESS, {'count': 1}

        except self.view.model.DoesNotExist:
            return RETCODE.NOT_FOUND, None

    async def insert(self, data):
        if not len(data):
            return RETCODE.INVALID_PARAMS, None
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
                return RETCODE.SUCCESS, item.to_dict()
            except self.view.model.ErrorSavingData:
                db.rollback()
                return RETCODE.FAILED, None


class PeeweeView(View):
    model = None

    def __init__(self, request):
        super().__init__(request)
        self._sql = PeeweeSQLFunctions(self)

    # noinspection PyProtectedMember
    @staticmethod
    async def _fetch_fields(cls_or_self):
        if cls_or_self.model:
            cls_or_self.fields = cls_or_self.model._meta.fields
            cls_or_self.table_name = cls_or_self.model._meta.db_table
