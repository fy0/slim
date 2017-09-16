import re
import time
from .async import async_corun, async_run
from .binhex import to_bin, to_hex
from .pagination import pagination_calc

RegexPatternType = type(re.compile(''))


def dict_filter(obj, keys):
    return {k: v for k, v in obj.items() if k in keys}


def time_readable():
    x = time.localtime(time.time())
    return time.strftime('%Y-%m-%d %H:%M:%S', x)


# noinspection PyUnresolvedReferences
class MetaClassForInit(type):
    def __new__(mcs, *args, **kwargs):
        new_class = super().__new__(mcs, *args, **kwargs)
        new_class.cls_init()
        return new_class

