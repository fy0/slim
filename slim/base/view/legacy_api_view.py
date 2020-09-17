from typing import Any, Union, Optional

from slim import json_ex_dumps
from slim.base.view.base_view import BaseView
from slim.base.web import JSONResponse, Response, StreamReadFunc
from slim.ext.decorator import deprecated
from slim.retcode import RETCODE
from slim.utils import sentinel


class LegacyAPIView(BaseView):
    ret_val: Optional[Any]

    async def _prepare(self):
        await super(LegacyAPIView, self)._prepare()
        self.ret_val: Any = None
    
    @property
    def retcode(self):
        if self.is_finished:
            return self.ret_val['code']

    def finish(self, code: int, data=sentinel, msg=sentinel, *, headers=None):
        """
        Set response as {'code': xxx, 'data': xxx}
        :param code: Result code
        :param data: Response data
        :param msg: Message, optional
        :param headers: Response header
        :return:
        """
        if data is sentinel:
            data = RETCODE.txt_cn.get(code, None)
        if msg is sentinel and code != RETCODE.SUCCESS:
            msg = RETCODE.txt_cn.get(code, None)
        body = {'code': code, 'data': data}  # for access in inhreads method
        if msg is not sentinel:
            body['msg'] = msg

        self.ret_val = body
        self.response = JSONResponse(data=body, json_dumps=json_ex_dumps, headers=headers, cookies=self._cookie_set)

    def finish_json(self, data: Any, *, status: int = 200, headers=None):
        self.ret_val = data
        self.response = JSONResponse(data=data, json_dumps=json_ex_dumps, headers=headers, status=status,
                                     cookies=self._cookie_set)

    def finish_raw(self, data: Union[bytes, str, StreamReadFunc] = b'', status: int = 200, content_type: str = 'text/plain', *,
                   headers=None):
        """
        Set raw response
        :param headers:
        :param data:
        :param status:
        :param content_type:
        :return:
        """
        self.ret_val = data
        self.response = Response(data=data, status=status, content_type=content_type, headers=headers, cookies=self._cookie_set)

    @property
    @deprecated('deprecated, use function arguments to instead')
    def route_info(self):
        """
        info matched by router
        :return:
        """
        return self._legacy_route_info_cache
