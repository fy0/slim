from typing import Type, Union

import peewee
from schematics.models import Model, ValidationError, ConversionError
from schematics.types import StringType, NumberType, DateTimeType, ModelType, BaseType, DictType, BooleanType, \
    ListType, IntType, FloatType, DateType
from slim.base.sqlquery import SQLForeignKey
from slim.utils.schematics_ext import BlobType, JSONListType, JSONDictType, JSONType

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


pv3 = peewee.__version__[0] >= '3'


# noinspection PyProtectedMember
def get_pv_pk_name(the_model):
    # http://docs.peewee-orm.com/en/latest/peewee/changes.html#fields
    pk = the_model._meta.primary_key
    return pk.column_name if pv3 else pk.db_column


# noinspection PyProtectedMember
def get_pv_table_name(the_model):
    meta = the_model._meta
    return meta.table_name if pv3 else meta.db_table


def field_class_to_schematics_field(field: peewee.Field) -> BaseType:
    if isinstance(field, peewee.ForeignKeyField):
        field = field.rel_field

    kwargs = {}

    # 检查是否 require
    if not ((field.default is not None) or field.null or field.sequence or isinstance(field, peewee.AutoField)):
        kwargs['required'] = True

    if field.help_text:
        kwargs['metadata'] = {'description': field.help_text}

    if isinstance(field, peewee.IntegerField):
        return IntType(**kwargs)
    elif isinstance(field, peewee.FloatField):
        return FloatType(**kwargs)
    elif isinstance(field, (PG_JSONField, PG_BinaryJSONField, SQLITE_JSONField)):
        # 注意 SQLITE_JSONField 是一个 _StringField 所以要提前
        return JSONType(**kwargs)
        # HStore 貌似才应该对应 dict，json可以对应任意类型
        # return JSONDictType(StringType, **kwargs)
    elif isinstance(field, peewee.DateTimeField):
        return DateTimeType(**kwargs)
    elif isinstance(field, peewee.DateField):
        return DateType(**kwargs)
    elif isinstance(field, peewee._StringField):
        return StringType(**kwargs)
    elif isinstance(field, peewee.BooleanField):
        return BooleanType(**kwargs)
    elif isinstance(field, peewee.BlobField):
        return BlobType(**kwargs)
    elif isinstance(field, PG_ArrayField):
        field: PG_ArrayField
        return JSONListType(field_class_to_schematics_field(field._ArrayField__field), **kwargs)


# noinspection PyProtectedMember
def get_pv_model_info(model: Union[peewee.Model, Type[peewee.Model]]):
    new_model_cls: Type[Model] = type(model.__class__.__name__ + 'Validator', (Model,), {})
    foreign_keys = {}
    peewee_fields = {}

    ret = {
        'table_name': get_pv_table_name(model),
        'primary_key': get_pv_pk_name(model),
        'foreign_keys': foreign_keys,
        'data_model': new_model_cls,
        '_peewee_fields': peewee_fields
    }

    for name, field in model._meta.fields.items():
        if isinstance(field, peewee.ForeignKeyField):
            rm = field.rel_model
            name = '%s_id' % name
            # TODO: 这里可能会出问题
            foreign_keys[name] = [SQLForeignKey(get_pv_table_name(rm), get_pv_pk_name(rm))]

        peewee_fields[name] = field
        new_model_cls._append_field(name, field_class_to_schematics_field(field))

    return ret
