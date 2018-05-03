import json
from ..base.sqlquery import DataRecord
from .binhex import to_hex


def json_ex_default(o):
    if isinstance(o, memoryview):
        return o.hex()
    elif isinstance(o, bytes):
        return to_hex(o)
    elif isinstance(o, set):
        return list(o)
    elif isinstance(o, DataRecord):
        return o.to_dict()


def json_ex_dumps(obj, **kwargs):
    return json.dumps(obj, default=json_ex_default, **kwargs)
