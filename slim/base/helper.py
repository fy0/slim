import base64
import hashlib
import hmac
import logging

import msgpack


logger = logging.getLogger(__name__)
# __all__ = ('Route',)


def _value_encode(obj):
    return msgpack.dumps(obj, use_bin_type=True)


def _value_decode(data: bytes):
    return msgpack.loads(data, raw=False)


def _create_signature(secret: bytes, s):
    # hash = hashlib.blake2s(_signature_encode(s), key=secret[:32]) py3.6+
    m = hmac.new(secret, digestmod=hashlib.sha256)
    m.update(_value_encode(s))
    return m.hexdigest()


def create_signed_value(secret, s: [list, tuple]):
    sign = _create_signature(secret, s)
    return str(base64.b64encode(_value_encode(s + [sign])), 'utf-8')


def decode_signed_value(secret, s):
    s = _value_decode(base64.b64decode(bytes(s, 'utf-8')))
    data = s[:-1]
    sign = _create_signature(secret, data)
    if sign != s[-1]:
        return None
    return data
