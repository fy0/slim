from slim.base.types.doc import ApplicationDocInfo
from slim.ext.decorator import D
from .base.app import Application
from .base.web import CORSOptions
# from slim.ext.permission import ALL_PERMISSION, EMPTY_PERMISSION, A
from .utils.json_ex import json_ex_dumps, json_ex_default
from . import base
from . import ext
from . import utils
from . import view

__version__ = '0.7.0a8'
