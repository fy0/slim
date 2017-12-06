import json
from .binhex import to_hex
from json import JSONEncoder


class JEncoder(JSONEncoder):
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
    json._default_encoder = JEncoder(
        skipkeys=False,
        ensure_ascii=True,
        check_circular=True,
        allow_nan=True,
        indent=None,
        separators=None,
        default=None,
    )
