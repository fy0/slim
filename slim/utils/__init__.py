import re
import time
from .async import async_corun, async_run
from .binhex import to_bin, to_hex
from .pagination import pagination_calc
from .cls_init import MetaClassForInit

RegexPatternType = type(re.compile(''))


def dict_filter(obj, keys):
    return {k: v for k, v in obj.items() if k in keys}


def time_readable():
    x = time.localtime(time.time())
    return time.strftime('%Y-%m-%d %H:%M:%S', x)
