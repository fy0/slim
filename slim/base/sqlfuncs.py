import logging
from typing import Tuple

from slim.base.permission import AbilityRecord

logger = logging.getLogger(__name__)


class AbstractSQLFunctions:
    def __init__(self, view):
        self.err = None
        self.view = view
        self.request = view.request

    async def select_paginated_list(self, info, size, page):
        """ tips: size == -1 means infinite """
        raise NotImplementedError()

    async def select_one(self, select_info) -> Tuple[object, AbilityRecord]:
        raise NotImplementedError()
        # code, item

    async def update(self, select_info, data):
        raise NotImplementedError()
        # code, item

    async def insert(self, data) -> Tuple[object, AbilityRecord]:
        raise NotImplementedError()
        # code, record

    # noinspection PyMethodMayBeStatic
    def done(self, code, data=None):
        return code, data
