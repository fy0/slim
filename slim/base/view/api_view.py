from typing import Union

from slim import json_ex_dumps
from slim.base.view.base_view import BaseView
from slim.base.web import JSONResponse, StreamReadFunc, Response
from slim.utils import sentinel


class APIView(BaseView):
    def finish(self, data=sentinel, status: int = 200, *, headers=None):
        """
        Set response as {'code': xxx, 'data': xxx}
        :param status: http status code
        :param data: Response data
        :param headers: Response header
        :return:
        """
        self.response = JSONResponse(data=data, status=status, headers=headers, cookies=self._cookie_set)

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
        self.response = Response(data=data, status=status, content_type=content_type, headers=headers, cookies=self._cookie_set)
