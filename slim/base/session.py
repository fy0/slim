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

    def __setattr__(self, key, value):
        if key not in ('_view', '_data'):
            raise AttributeError("use session[%r] = ... to set value" % key)
        super().__setattr__(key, value)

    def __contains__(self, item):
        return item in self._data

    async def load(self):
        raise NotImplementedError

    async def save(self):
        raise NotImplementedError

    @classmethod
    async def get_session(cls, view):
        session = cls(view)
        await session.load()
        return session


class CookieSession(BaseSession):
    async def load(self):
        self._data = self._view.get_secure_cookie('s') or {}

    async def save(self):
        self._view.set_secure_cookie('s', self._data)


class MemoryTokenSession(BaseSession):
    data = {}

    def load(self):
        token = self._view.headers.get('AccessToken')
        return self.data.get(token)

    def save(self):
        pass

    def new(self, token):
        self.data[token] = {}
