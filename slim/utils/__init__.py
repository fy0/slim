import random
import re
import string
import time
from .async import async_corun, async_run
from .binhex import to_bin, to_hex
from .cls_init import MetaClassForInit
from .pagination import pagination_calc
from .state_obj import StateObject
from .myobjectid import ObjectID


try:
    import msgpack
except ImportError:
    # noinspection SpellCheckingInspection
    from . import umsgpack as msgpack


RegexPatternType = type(re.compile(''))


def random_str(random_length=16, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(random_length))


def dict_filter(obj, keys):
    return {k: v for k, v in obj.items() if k in keys}


def time_readable():
    x = time.localtime(time.time())
    return time.strftime('%Y-%m-%d %H:%M:%S', x)


def bool_parse(val):
    is_true = val in ('true', 'True', '1')
    is_false = val in ('false', 'False', '0')
    if not (is_true or is_false):
        raise ValueError("Invalid boolean value: %r" % val)
    return is_true
