import json
import random
import re
import string
import sys
import time
from typing import Optional

from .async_run import *
from .binhex import to_bin, to_hex, get_bytes_from_blob
from .cls_init import MetaClassForInit
from .pagination import pagination_calc
from .state_obj import StateObject
from .myobjectid import ObjectID
from .customid import CustomID

try:
    import msgpack
except ImportError:
    # noinspection SpellCheckingInspection
    from . import umsgpack as msgpack

is_py36 = sys.version_info[0] >= 3 and sys.version_info[1] >= 6

RegexPatternType = type(re.compile(''))
sentinel = object()


def random_str(random_length=16, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(random_length))


def dict_filter(obj, keys):
    return {k: v for k, v in obj.items() if k in keys}


def dict_filter_inplace(obj, keys):
    to_remove = []
    for i in obj.keys():
        if i not in keys:
            to_remove.append(i)

    for i in to_remove:
        del obj[i]


def time_readable():
    x = time.localtime(time.time())
    return time.strftime('%Y-%m-%d %H:%M:%S', x)


class BoolParser:
    def __new__(cls, val):
        is_true = val in ('true', 'True', '1')
        is_false = val in ('false', 'False', '0')
        if not (is_true or is_false):
            raise ValueError("Invalid boolean value: %r" % val)
        return is_true


class BlobParser:
    def __new__(cls, val):
        if isinstance(val, (memoryview, bytes)):
            return val
        # FIX: 其实这可能有点问题，因为None是一个合法的值
        if val is None:
            return val
        # 同样的，NotImplemented 似乎可能是一个非法值
        # 很有可能不存在一部分是 NotImplemented 另一部分不是的情况
        if val is NotImplemented:
            return
        if isinstance(val, str):
            is_hex = all(c in string.hexdigits for c in val)
            if not is_hex:
                raise ValueError("Invalid hexadecimal string: %r" % val)
            if len(val) % 2 == 1:
                val = '0' + val
            return to_bin(val)


class JSONParser:
    def __new__(cls, val):
        if isinstance(val, str):
            return json.loads(val)
        return val
