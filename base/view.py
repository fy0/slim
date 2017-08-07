from aiohttp import web

from mapi.base.session import SimpleSession
from ..retcode import RETCODE
from ..utils import time_readable, ResourceException, _valid_sql_operator, _MetaClassForInit
from .permission import Permission, FakePermission


class MView(metaclass=_MetaClassForInit):
    """
    应在 cls_init 时完成全部接口的扫描与wrap函数创建
    并在wrapper函数中进行实例化，传入 request 对象
    """
    _interface = {}
    _session_class = SimpleSession

    @classmethod
    def use(cls, name, method_or_lst, url=None):
        """ interface helper function"""
        if type(method_or_lst) == list:
            val = method_or_lst
        else:
            val = {'method': method_or_lst, 'url': url} if url else method_or_lst
        cls._interface[name] = val

    @classmethod
    def use_lst(cls, name):
        cls.use(name, [
            {'method': 'GET', 'url': '/%s/{page}' % name},
            {'method': 'GET', 'url': '/%s/{page}/{size}' % name},
        ])

    @classmethod
    def discard(cls, name):
        """ interface helper function"""
        cls._interface.pop(name, None)

    @classmethod
    def interface(cls):
        cls.use('get', 'GET')
        cls.use_lst('list')
        cls.use('set', 'POST')
        cls.use('new', 'POST')
        cls.use('del', 'POST')

    @classmethod
    def cls_init(cls):
        cls._interface = {}
        cls.interface()

    def __init__(self, request):
        self.request = request
        self.ret_val = None
        self.session = self._session_class(self)
        self._cookie_set = None

    async def prepare(self):
        pass

    def finish(self, code, data=None):
        self.session.flush()
        self.ret_val = web.json_response({'code': code, 'data': data})
        for i in self._cookie_set or ():
            if i[0] == 'set':
                self.ret_val.set_cookie(i[1], i[2], secure=False) # secure not work
            else:
                self.ret_val.del_cookie(i[1], secure=False)

    def set_cookie(self, key, value, secure=False):
        if self._cookie_set is None:
            self._cookie_set = []
        self._cookie_set.append(('set', key, value, secure,))

    def del_cookie(self, key, secure=False):
        if self._cookie_set is None:
            self._cookie_set = []
        self._cookie_set.append(('del', key, secure,))
