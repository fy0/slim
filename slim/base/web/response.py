import asyncio
import hashlib
import os
from dataclasses import dataclass, field
from email.utils import formatdate
from mimetypes import guess_type
from types import FunctionType
from typing import Callable, AsyncIterator, Tuple, Union, Dict, Any

import aiofiles

from ...utils import sentinel
from ...utils.json_ex import json_ex_dumps
from .. import const
from ..types.asgi import Scope, Receive, Send
from ...exception import InvalidResponse

StreamReadFunc = Callable[[], AsyncIterator[Tuple[bytes, bool]]]  # data, has_more


@dataclass
class Response:
    status: int = 200
    data: Union[str, bytes, StreamReadFunc] = b''
    headers: Dict[str, Any] = None
    content_type: str = 'text/plain'
    cookies: Dict[str, Dict] = None

    written: int = 0

    async def get_reader(self, data) -> StreamReadFunc:
        """
        Get reader function
        :return:
        """
        if asyncio.iscoroutinefunction(data):
            return data

        if isinstance(data, str):
            body = data.encode('utf-8')
        elif isinstance(data, bytes):
            body = data
        elif data is sentinel:
            body = b''
        else:
            raise InvalidResponse()

        async def stream_read() -> AsyncIterator[Tuple[bytes, bool]]:
            yield body, False

        return stream_read

    def build_headers(self):
        headers = [
            # TODO: bytes convert cache
            [const.CONTENT_TYPE.encode('utf-8'), self.content_type.encode('utf-8')]
         ]

        if self.cookies:
            set_cookie = const.SET_COOKIE.encode('utf-8')
            for k, v in self.cookies.items():
                value = f"{v['name']}={v['value']}"

                if 'expires' in v:
                    value += f"; Expires={v['expires']}"

                if 'max-age' in v:
                    value += f"; Max-Age={v['max-age']}"

                if 'domain' in v:
                    value += f"; Domain={v['domain']}"

                if 'path' in v:
                    value += f"; Path={v['path']}"

                if v.get('secure'):
                    value += f"; Secure"

                if v.get('httponly'):
                    value += f"; HttpOnly"

                headers.append([set_cookie, value.encode('utf-8')])

        if self.headers:
            for k, v in self.headers.items():
                headers.append([k, v])

        headers_new = []
        for a, b in headers:
            if not isinstance(a, bytes):
                a = str(a).encode('utf-8')
            if not isinstance(b, bytes):
                b = str(b).encode('utf-8')
            headers_new.append([a, b])

        return headers_new

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = self.build_headers()
        reader = await self.get_reader(self.data)
        await send({
            "type": "http.response.start",
            "status": self.status,
            "headers": headers,
        })

        async for chunk, more_body in reader():
            self.written += len(chunk)
            ret = {
                "type": "http.response.body",
                "body": chunk
            }
            if more_body:
                ret["more_body"] = more_body
            await send(ret)


@dataclass
class JSONResponse(Response):
    data: Any = None
    content_type: str = 'application/json'
    json_dumps: FunctionType = json_ex_dumps

    async def get_reader(self, data) -> StreamReadFunc:
        if data is not sentinel:
            data = self.json_dumps(data)
        return await super().get_reader(data)


@dataclass
class FileResponse(Response):
    static_file_path: str = None
    stat_result: os.stat_result = None

    content_type = None
    filename: str = None
    chunk_size = 4096
    headers: Dict[str, Any] = field(default_factory=lambda: {})

    def __post_init__(self):
        if self.content_type is None:
            self.content_type = guess_type(self.static_file_path)[0] or "text/plain"

        if not self.filename:
            self.filename = os.path.basename(self.static_file_path)

        if self.filename is not None:
            content_disposition = 'attachment; filename="{}"'.format(self.filename)
            self.headers.setdefault("content-disposition", content_disposition)

        if self.stat_result is not None:
            self.set_stat_headers(self.stat_result)

    def set_stat_headers(self, stat_result):
        content_length = str(stat_result.st_size)
        last_modified = formatdate(stat_result.st_mtime, usegmt=True)
        etag_base = str(stat_result.st_mtime) + "-" + str(stat_result.st_size)
        etag = hashlib.md5(etag_base.encode()).hexdigest()
        self.headers.setdefault("content-length", content_length)
        self.headers.setdefault("last-modified", last_modified)
        self.headers.setdefault("etag", etag)

    async def get_reader(self, data) -> StreamReadFunc:
        async def stream_read() -> AsyncIterator[Tuple[bytes, bool]]:
            async with aiofiles.open(self.static_file_path, mode="rb") as file:
                more_body = True
                while more_body:
                    chunk = await file.read(self.chunk_size)
                    more_body = len(chunk) == self.chunk_size
                    yield chunk, more_body

        return stream_read
