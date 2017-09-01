import logging

logger = logging.getLogger(__name__)


class BaseSession:
    def __init__(self, view):
        self._view = view
        self._data = None

    def __delitem__(self, key):
        del self._data[key]

    def __getitem__(self, key):
        return self._data.get(key)

    def __setitem__(self, key, value):
        self._data[key] = value

    async def load(self):
        raise NotImplementedError

    async def save(self):
        raise NotImplementedError

    @classmethod
    async def get_session(cls, view):
        session = cls(view)
        await session.load()
        return session


class SimpleSession(BaseSession):
    async def load(self):
        self._data = self._view.get_secure_cookie('s') or {}

    async def save(self):
        self._view.set_secure_cookie('s', self._data)
