import logging
from abc import abstractmethod
from typing import Tuple

from slim.base.permission import AbilityRecord

logger = logging.getLogger(__name__)


class AbstractSQLFunctions:
    def __init__(self, view_cls):
        self.err = None
        self.vcls = view_cls

    def reset(self):
        self.err = None

    @abstractmethod
    async def select_paginated_list(self, info, size, page):
        """ tips: size == -1 means infinite """
        raise NotImplementedError()
        # code, data with items

    @abstractmethod
    async def select_one(self, select_info) -> Tuple[object, AbilityRecord]:
        raise NotImplementedError()
        # code, item

    @abstractmethod
    async def update(self, select_info, data):
        raise NotImplementedError()
        # code, item

    @abstractmethod
    async def insert(self, data) -> Tuple[object, AbilityRecord]:
        raise NotImplementedError()
        # code, record

    @abstractmethod
    async def delete(self, select_info):
        raise NotImplementedError()
        # code, count

    @staticmethod
    def convert_list_result(format, data):
        lst = []
        get_values = lambda x: list(x.values())
        for record in data['items']:
            item = record.to_dict()

            if format == 'array':
                item = get_values(item)

            lst.append(item)
        return lst
