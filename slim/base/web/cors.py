from dataclasses import dataclass
from typing import Optional, Sequence, Iterable

import typing

from .. import const

if typing.TYPE_CHECKING:
    from .request import ASGIRequest


@dataclass
class CORSOptions:
    host: str
    allow_credentials: bool = False
    expose_headers: Optional[Sequence] = None
    allow_headers: Sequence = ()
    max_age: Optional[int] = None
    allow_methods: Optional[Sequence] = '*'

    def pack_headers(self, request: 'ASGIRequest'):
        def solve(val):
            if isinstance(val, str):
                return val
            elif isinstance(val, Iterable):
                return ','.join(val)

        req_headers = request.headers

        headers = {
            const.ACCESS_CONTROL_ALLOW_ORIGIN: req_headers.get('origin'),
            const.ACCESS_CONTROL_ALLOW_CREDENTIALS: b'true' if self.allow_credentials else b'false'
        }

        if request.method == 'OPTIONS':
            if self.allow_headers:
                if self.allow_headers == '*':
                    headers[const.ACCESS_CONTROL_ALLOW_HEADERS] = req_headers.get('access-control-request-headers') or '*'
                else:
                    headers[const.ACCESS_CONTROL_ALLOW_HEADERS] = solve(self.allow_headers)

            if self.allow_methods:
                if self.allow_methods == '*':
                    headers[const.ACCESS_CONTROL_ALLOW_METHODS] = req_headers.get('access-control-request-method') or request.method
                else:
                    headers[const.ACCESS_CONTROL_ALLOW_METHODS] = self.allow_methods

        else:
            if self.expose_headers:
                # headers[const.ACCESS_CONTROL_EXPOSE_HEADERS] = solve(self.expose_headers)
                headers[const.ACCESS_CONTROL_EXPOSE_HEADERS] = b''

        if self.max_age:
            headers[const.ACCESS_CONTROL_MAX_AGE] = self.max_age

        return headers