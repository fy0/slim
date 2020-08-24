import os
import stat
from aiofiles.os import stat as aio_stat

from slim.base.web import FileResponse, Response, ASGIRequest


class StaticFileResponder:
    def __init__(self, fullpath, static_path: str):
        self.fullpath = fullpath
        self.static_path = static_path

    async def solve(self, request: ASGIRequest, path):
        static_file_path = os.path.join(self.static_path, path)
        try:
            stat_result = await aio_stat(static_file_path)
        except FileNotFoundError:
            return Response(404, b"Not Found")

        mode = stat_result.st_mode
        if not stat.S_ISREG(mode):
            return Response(404, b"Not Found")

        return FileResponse(static_file_path=static_file_path, stat_result=stat_result)
