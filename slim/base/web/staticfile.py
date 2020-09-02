import os
import stat
from urllib.parse import urljoin

from aiofiles.os import stat as aio_stat
from multipart import multipart

from .response import Response, FileResponse
from .request import ASGIRequest


class StaticFileResponder:
    def __init__(self, fullpath, static_path: str):
        self.fullpath = fullpath
        self.static_path = static_path

    async def solve(self, request: ASGIRequest, path):
        ext_path = urljoin('.', path)
        if ext_path.startswith('/'):
            ext_path = ext_path[1:]
        static_file_path = os.path.join(self.static_path, ext_path)

        try:
            stat_result = await aio_stat(static_file_path)
        except FileNotFoundError:
            return Response(404, b"Not Found")

        mode = stat_result.st_mode
        if not stat.S_ISREG(mode):
            return Response(404, b"Not Found")

        return FileResponse(static_file_path=static_file_path, stat_result=stat_result)


class FileField:
    def __init__(self, field: multipart.File):
        self._field = field
        field.file_object.seek(0)

    @property
    def field_name(self):
        return _to_str(self._field.field_name)

    @property
    def file_name(self):
        return _to_str(self._field.file_name)

    @property
    def actual_file_name(self):
        return _to_str(self._field.actual_file_name)

    @property
    def file(self):
        return self._field.file_object

    @property
    def size(self):
        return self._field.size


def _to_str(s):
    if isinstance(s, bytes):
        return s.decode('utf-8')
    return s