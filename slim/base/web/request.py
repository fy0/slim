from dataclasses import dataclass

from multidict import CIMultiDict, istr

from ..types.asgi import Scope, Receive, Send


@dataclass
class ASGIRequest:
    scope: Scope
    receive: Receive
    send: Send

    _headers_cache = None

    @property
    def method(self):
        return self.scope['method']

    @property
    def headers(self) -> CIMultiDict:
        """
        Get headers
        """
        if self._headers_cache is None:
            headers = CIMultiDict()
            for k, v in self.scope['headers']:
                k: bytes
                v: bytes
                headers.add(istr(k.decode('utf-8')), v.decode('utf-8'))
            self._headers_cache = headers
        return self._headers_cache
