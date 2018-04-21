import logging
from abc import abstractmethod
from enum import Enum
from typing import Tuple, Dict, Iterable
from .sqlquery import SQLQueryInfo, SQLValuesToWrite

logger = logging.getLogger(__name__)


class UpdateInfo:
    def __init__(self, key, op, val):
        assert op in ('incr', 'to')
        self.key = key
        self.op = op
        self.val = val


class DataRecord:
    def __init__(self, table_name, val):
        self.table = table_name
        self.val = val

    def get(self, key):
        raise NotImplementedError()

    def keys(self):
        raise NotImplementedError()

    def has(self, key):
        raise NotImplementedError()

    def to_dict(self, available_columns=None) -> Dict:
        raise NotImplementedError()


class AbstractSQLFunctions:
    def __init__(self, view_cls):
        self.vcls = view_cls

    @abstractmethod
    async def select(self, info: SQLQueryInfo, size=1, page=1) -> (Tuple[DataRecord], int):
        """
        Select from database
        :param info:
        :param size: -1 means infinite
        :param page:
        :return:
        """
        raise NotImplementedError()

    @abstractmethod
    async def update(self, records: Iterable[DataRecord], values: SQLValuesToWrite):
        raise NotImplementedError()
        # code, item

    @abstractmethod
    async def insert(self, values: SQLValuesToWrite):
        raise NotImplementedError()
        # code, record

    @abstractmethod
    async def delete(self, records: Iterable[DataRecord]):
        raise NotImplementedError()
        # code, count
