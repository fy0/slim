import string
from schematics import Model
from schematics.exceptions import ConversionError
from schematics.types import HashType

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


def schematics_to_json_schema(model: Model):
    for k, v in model._fields.items():
        pass

    properties = {}

    ret = {
        "type": "object",
        "properties": properties
    }

    return ret
