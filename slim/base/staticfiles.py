import os
import stat
from aiofiles.os import stat as aio_stat

from slim.base.web import FileResponse, Response
from slim.utils.types import Receive, Send, Scope, ASGIInstance


class StaticFile:
    def __init__(self, *, path: str) -> None:
        self.path = path

    def __call__(self, scope: Scope) -> ASGIInstance:
        assert scope["type"] == "http"
        if scope["method"] not in ("GET", "HEAD"):
            return Response(body="Method Not Allowed", status=405)
        return _StaticFileResponder(scope, path=self.path)


class StaticFiles:
    def __init__(self, *, directory: str) -> None:
        self.directory = directory
        self.config_checked = False

    def __call__(self, scope: Scope) -> ASGIInstance:
        assert scope["type"] == "http"
        if scope["method"] not in ("GET", "HEAD"):
            return Response(body="Method Not Allowed", status=405)
        path = os.path.normpath(os.path.join(scope["path"].split("/")[-1]))
        if path.startswith(".."):
            return Response(body="Not Found", status=404)
        path = os.path.join(self.directory, path)
        if self.config_checked:
            check_directory = None
        else:
            check_directory = self.directory
            self.config_checked = True
        return _StaticFilesResponder(scope, path=path, check_directory=check_directory)


class _StaticFileResponder:
    def __init__(self, scope: Scope, path: str) -> None:
        self.scope = scope
        self.path = path

    async def __call__(self, receive: Receive, send: Send) -> None:
        try:
            stat_result = await aio_stat(self.path)
        except FileNotFoundError:
            raise RuntimeError("StaticFile at path '%s' does not exist." % self.path)
        else:
            mode = stat_result.st_mode
            if not stat.S_ISREG(mode):
                raise RuntimeError("StaticFile at path '%s' is not a file." % self.path)

        response = FileResponse(self.path, stat_result=stat_result)
        await response(receive, send)


class _StaticFilesResponder:
    def __init__(self, scope: Scope, path: str, check_directory: str = None) -> None:
        self.scope = scope
        self.path = path
        self.check_directory = check_directory
        # TODO: 临时方案，兼容日志输出
        self.status = 200

    async def check_directory_configured_correctly(self) -> None:
        """
        Perform a one-off configuration check that StaticFiles is actually
        pointed at a directory, so that we can raise loud errors rather than
        just returning 404 responses.
        """
        directory = self.check_directory
        try:
            stat_result = await aio_stat(directory)
        except FileNotFoundError:
            raise RuntimeError("StaticFiles directory '%s' does not exist." % directory)
        if not (stat.S_ISDIR(stat_result.st_mode) or stat.S_ISLNK(stat_result.st_mode)):
            raise RuntimeError("StaticFiles path '%s' is not a directory." % directory)

    async def __call__(self, receive: Receive, send: Send) -> None:
        if self.check_directory is not None:
            await self.check_directory_configured_correctly()

        try:
            stat_result = await aio_stat(self.path)
        except FileNotFoundError:
            self.status = 404
            response = Response(body="Not Found", status=404)  # type: Response
        else:
            mode = stat_result.st_mode
            if not stat.S_ISREG(mode):
                self.status = 404
                response = Response(body="Not Found", status=404)
            else:
                response = FileResponse(self.path, stat_result=stat_result)

        await response(receive, send)
