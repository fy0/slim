import json

import asyncio

import binascii
import peewee
from playhouse.postgres_ext import BinaryJSONField
from playhouse.shortcuts import model_to_dict

from mapi.retcode import RETCODE
from mapi.utils import to_bin
from ...base.view import MView, BaseSQLFunctions


class BaseModel(peewee.Model):
    def to_dict(self):
        return model_to_dict(self)


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


class PeeweeSQLFunctions(BaseSQLFunctions):
    def _get_pw_args(self, args):
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

    async def select_one(self, si):
        pw_args = self._get_pw_args(si['args'])
        if self.err: return self.err
        try:
            return RETCODE.SUCCESS, self.view.model.get(*pw_args).to_dict()
        except self.view.model.DoesNotExist:
            return RETCODE.NOT_FOUND, None

    async def select_count(self, si):
        pw_args = self._get_pw_args(si['args'])
        if self.err: return self.err
        q = self.view.model.select().where(*pw_args) if pw_args else self.view.model.select()
        return RETCODE.SUCCESS, q.count()

    async def select_list(self, si, size, offset, *, page=None):
        model = self.view.model
        pw_args = self._get_pw_args(si['args'])
        if self.err: return self.err
        q = model.select().where(*pw_args) if pw_args else model.select()
        #.limit(size).offset(size * (page - 1)).sql()
        return RETCODE.SUCCESS, map(model.to_dict, q.paginate(page, size))

    async def update(self, si, data):
        pw_args = self._get_pw_args(si['args'])
        if self.err: return self.err

        try:
            item = self.view.model.get(*pw_args)
            db = self.view.model._meta.database
            with db.atomic() as transaction:
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

        with db.atomic() as transaction:
            try:
                item = self.view.model.create(**kwargs)
                return RETCODE.SUCCESS, item.to_dict()
            except self.view.model.ErrorSavingData:
                db.rollback()
                return RETCODE.FAILED, None


class PeeweeMView(MView):
    model = None
    sql_cls = PeeweeSQLFunctions

    @staticmethod
    async def _fetch_fields(cls_or_self):
        if cls_or_self.model:
            cls_or_self.fields = cls_or_self.model._meta.fields
            cls_or_self.table_name = cls_or_self.model._meta.db_table
