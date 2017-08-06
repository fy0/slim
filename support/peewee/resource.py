import json

import peewee
from playhouse.postgres_ext import BinaryJSONField
from playhouse.shortcuts import model_to_dict

from ...retcode import RETCODE
from ...utils import pagination_calc_peewee
from ...base.resource import Resource


class BaseModel(peewee.Model):
    def to_dict(self):
        return model_to_dict(self)


_peewee_method_map = {
    # '+': '__pos__',
    # '-': '__neg__',
    '==': '__eq__',
    '!=': '__ne__',
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
}


class PeeweeResource(Resource):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.fields = model._meta.fields if model else {}

    def _query_convert(self, params):
        args = []
        for k, v in params.items():
            info = k.split('.', 1)
            if info[0] in self.fields:
                field = self.fields[info[0]]
                if len(info) > 1:
                    args.append(getattr(field, _peewee_method_map[info[1]])(v))
                else:
                    args.append(field == v)
        return args

    def _get_one(self, request):
        ret = self._query_convert(request.query)
        try:
            return self.model.get(*ret)
        except self.model.DoesNotExist:
            pass

    def _get_list(self, request):
        ret = self._query_convert(request.query)
        return self.model.select().where(*ret) if ret else self.model.select()

    async def get(self, request):
        item = self._get_one(request)
        if item:
            self.finish(RETCODE.SUCCESS, item.to_dict())
        else:
            self.finish(RETCODE.NOT_FOUND)

    async def set(self, request):
        item = self._get_one(request)
        if item:
            data = await request.post()
            for k, v in data.items():
                if k in self.fields:
                    setattr(item, k, self.query_and_store_handle(k, v))
            item.save()
            return self.finish(RETCODE.SUCCESS, item.to_dict())
        else:
            return self.finish(RETCODE.NOT_FOUND)

    async def new(self, request):
        item = self.model()
        if item:
            data = await request.post()
            if not len(data):
                return self.finish(RETCODE.INVALID_PARAMS)
            for k, v in data.items():
                if k in self.fields:
                    field = self.fields[k]
                    if isinstance(field, BinaryJSONField):
                        setattr(item, k, json.loads(v))
                    else:
                        setattr(item, k, v)
            item.save()
            self.finish(RETCODE.SUCCESS, item.to_dict())
        else:
            self.finish(RETCODE.NOT_FOUND)

    async def list(self, request):
        q = self._get_list(request)
        page = request.match_info.get('page', "1")

        if not page.isdigit():
            return self.finish(RETCODE.INVALID_PARAMS)

        data = await request.post()
        pg = pagination_calc_peewee(q.count(), q, self.LIST_PAGE_SIZE, page)
        pg["items"] = list(map(self.model.to_dict, pg["items"]))
        self.finish(RETCODE.SUCCESS, pg)
