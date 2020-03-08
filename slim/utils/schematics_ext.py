import json
import string
from typing import Dict, Type

from schematics import Model
from schematics.exceptions import ConversionError
from schematics.types import HashType, BaseType, NumberType, UUIDType, StringType, IntType, LongType, FloatType, \
    DecimalType, MD5Type, SHA1Type, BooleanType, DateType, DateTimeType, UTCDateTimeType, TimestampType, TimedeltaType, \
    GeoPointType, MultilingualStringType, EmailType, IPv4Type, IPv6Type, URLType, IPAddressType, MACAddressType, \
    ListType, DictType

from slim.utils import to_bin


class BlobType(HashType):
    def to_native(self, value, context=None):
        if isinstance(value, (memoryview, bytes)):
            return value

        if isinstance(value, str):
            is_hex = all(c in string.hexdigits for c in value)
            if not is_hex:
                raise ConversionError(self.messages['hash_hex'])
            if len(value) % 2 == 1:
                value = '0' + value
            return to_bin(value)


def _json_try_convert(value, err):
    if isinstance(value, (bytes, str)):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            raise ConversionError(err)
    return value


class JSONListType(ListType):
    def _convert(self, value, context):
        value = _json_try_convert(value, 'Could not interpret the value as a list')
        return super()._convert(value, context)


class JSONDictType(DictType):
    def _convert(self, value, context, safe=False):
        value = _json_try_convert(value, 'Could not interpret the value as a dict')
        return super()._convert(value, context, safe)


JSON_SCHEMA_TO_TYPES = {
    # https://json-schema.org/understanding-json-schema/reference/string.html#built-in-formats
    'string': {
        # Dates and times
        'date-time': DateTimeType,
        # - format: time
        'date': DateType,

        # Email addresses
        'email': EmailType,
        # - format: idn

        # Hostnames
        # - format: hostname
        # - format: idn-hostname

        # IP Addresses
        'ipv4': IPv4Type,
        'ipv6': IPv6Type,

        # Resource identifiers
        'uri': URLType,
        # - format: "uri-reference"

        # URI template
        # - format: uri-template

        # JSON Pointer

        # Regular Expressions
        'regex': StringType,

        # ?
        'uuid': UUIDType
    },
    'integer': NumberType
}

TYPES_TO_JSON_SCHEMA = {
    # types.compound
    ListType: {"type": "array"},
    DictType: {"type": "object"},

    # types.net
    IPv4Type: {"type": "string", "format": "ipv4"},
    IPv6Type: {"type": "string", "format": "ipv6"},
    # IPAddressType: {"type": "string"},
    MACAddressType: {"type": "string"},
    URLType: {"type": "string", "format": "uri"},
    EmailType: {"type": "string", "format": "email"},

    # types.base
    UUIDType: {"type": "string", "format": "uuid"},
    StringType: {"type": "string"},
    MultilingualStringType: None,

    IntType: {"type": "number"},
    LongType: {"type": "number"},
    FloatType: {"type": "number"},
    DecimalType: {"type": "number"},
    NumberType: {"type": "number"},

    MD5Type: {"type": "string"},  # no format
    SHA1Type: {"type": "string"},  # no format
    BlobType: {'type': "string", "example": "0f12", "pattern": "^([a-fA-F0-9]{2})+$"},
    HashType: None,

    BooleanType: {"type": "boolean"},

    GeoPointType: None,

    DateType: {"type": "string", "format": "date"},
    UTCDateTimeType: None,
    TimestampType: None,
    DateTimeType: {"type": "string", "format": "date-time"},
    TimedeltaType: None,
}


def schematics_field_to_parameter(field: BaseType):
    return {
        'name': field.name,
        'in': 'query',
        'description': '',
        'required': False
    }


string_type_mapping = {
    'min_length': 'minLength',
    'max_length': 'maxLength',
    'regex': 'pattern',
}

number_type_mapping = {
    'min_value': 'minimum',
    'max_value': 'maximum'
}

list_type_mapping = {
    'min_size': 'minItems',
    'max_size': 'maxItems'
}


def _convert_attr(base: Dict, field: BaseType, attr_mapping: Dict):
    for a, b in attr_mapping.items():
        val = getattr(field, a, None)
        if val is not None:
            base[b] = val
    return base


def field_metadata_assign(field, base):
    m = field.metadata
    if m and isinstance(m, dict):
        def assign(name):
            val = m.get(name)
            if val: base[name] = val

        assign('description')
        assign('schema')
        assign('example')

    return base


def schematics_field_to_schema(field: BaseType):
    base = TYPES_TO_JSON_SCHEMA.get(type(field))

    if base:
        base = base.copy()
    else:
        base = {}

    if isinstance(field, StringType):
        _convert_attr(base, field, string_type_mapping)
    elif isinstance(field, NumberType):
        _convert_attr(base, field, number_type_mapping)
    elif isinstance(field, ListType):
        _convert_attr(base, field, list_type_mapping)
    elif isinstance(field, DictType):
        pass

    field_metadata_assign(field, base)
    return base


def schematics_model_to_json_schema(model: Type[Model], generate_required=True):
    required = []
    properties = {}

    for name, field in model._fields.items():
        field: BaseType
        properties[name] = schematics_field_to_schema(field)
        if field.required: required.append(name)

    ret = {
        "type": "object",
        "properties": properties
    }

    if generate_required:
        ret['required'] = required

    return ret
