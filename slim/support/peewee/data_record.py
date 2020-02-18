import peewee
from playhouse.shortcuts import model_to_dict

from slim.base.sqlquery import DataRecord, ALL_COLUMNS
from slim.utils import get_bytes_from_blob, dict_filter


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
