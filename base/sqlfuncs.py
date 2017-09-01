import logging

logger = logging.getLogger(__name__)


class BaseSQLFunctions:
    def __init__(self, view):
        self.err = None
        self.view = view
        self.request = view.request

    async def select_pagination_list(self, info, size, page):
        raise NotImplementedError()

    async def select_one(self, select_info):
        raise NotImplementedError()
        # code, item

    async def update(self, select_info, data):
        raise NotImplementedError()
        # code, item

    async def insert(self, data):
        raise NotImplementedError()
        # code, item

    # noinspection PyMethodMayBeStatic
    def done(self, code, data=None):
        return code, data
