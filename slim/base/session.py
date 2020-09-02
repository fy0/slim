import logging
from abc import abstractmethod

logger = logging.getLogger(__name__)


class BaseSession:
    def __init__(self, view):
        self.key = None
        self._view = view
        self._data = {}

    def __delitem__(self, key):
        del self._data[key]

    def __getitem__(self, key):
        return self._data.get(key)

    def __setitem__(self, key, value):
        if self.key is None:
            raise AttributeError("Use `session.create` to set a key before store value")
        self._data[key] = value

    def __setattr__(self, key, value):
        if key not in ('view', '_data', 'key'):
            raise AttributeError("use session[%r] = ... to set value" % key)
        super().__setattr__(key, value)

    def __contains__(self, item):
        return item in self._data

    @abstractmethod
    async def get_key(self):
        raise NotImplementedError

    @abstractmethod
    async def load(self):
        raise NotImplementedError

    @abstractmethod
    async def save(self):
        raise NotImplementedError

    @classmethod
    async def get_session(cls, view):
        """
        Every request have a session instance
        :param view:
        :return:
        """
        session = cls(view)
        session.key = await session.get_key()
        session._data = await session.load() or {}
        return session


class CookieSession(BaseSession):
    async def get_key(self):
        pass

    async def load(self):
        return self._view.get_secure_cookie('s') or {}

    async def save(self):
        self._view.set_secure_cookie('s', self._data)


class BaseHeaderKeySession(BaseSession):
    async def get_key(self):
        return self._view.headers.get('Session', None)

    @abstractmethod
    async def new(self, key, expire=30):
        pass


class MemoryHeaderKeySession(BaseHeaderKeySession):
    data = {}

    def create(self, key, expire=30):
        if key not in MemoryHeaderKeySession.data:
            MemoryHeaderKeySession.data[key] = {}
        self.key = key

    async def load(self):
        return self.data.get(self.key, None)

    async def save(self):
        self.data[self.key] = self._data
