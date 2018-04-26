import json
from ..base.sqlquery import DataRecord
from .binhex import to_hex

is_patched = False


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


class JEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, memoryview):
            return o.hex()
        elif isinstance(o, bytes):
            return to_hex(o)
        elif isinstance(o, set):
            return super().default(list(o))
        return super().default(o)


def apply():
    """ patch json for memoryview/bytes/set/... """
    global is_patched
    if is_patched: return
    json._default_encoder = JEncoder(
        skipkeys=False,
        ensure_ascii=True,
        check_circular=True,
        allow_nan=True,
        indent=None,
        separators=None,
        default=None,
    )
    is_patched = True
