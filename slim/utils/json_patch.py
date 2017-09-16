import json
from .binhex import to_hex
from json import JSONEncoder


class JEncoder(JSONEncoder):
    def default(self, o):
        if type(o) == memoryview:
            return o.hex()
        if type(o) == bytes:
            return to_hex(o)
        return super().default(o)


def apply():
    json._default_encoder = JEncoder(
        skipkeys=False,
        ensure_ascii=True,
        check_circular=True,
        allow_nan=True,
        indent=None,
        separators=None,
        default=None,
    )
