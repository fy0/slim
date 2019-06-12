import logging
from abc import abstractmethod
from enum import Enum
from typing import Tuple, Dict, Iterable, Union, List, Sequence
from .sqlquery import SQLQueryInfo, SQLValuesToWrite, DataRecord

logger = logging.getLogger(__name__)


class AbstractSQLFunctions:
    def __init__(self, view_cls):
        self.vcls = view_cls

    @abstractmethod
    async def select_one(self, info: SQLQueryInfo) -> DataRecord:
        """
        Select one record from database
        :param info:
        :return: record
        """
        raise NotImplementedError()

    @abstractmethod
    async def select_page(self, info: SQLQueryInfo, size=1, page=1) -> Tuple[Tuple[DataRecord, ...], int]:
        """
        Select from database
        :param info:
        :param size: -1 means infinite
        :param page:
        :param need_count: if True, get count as second return value, otherwise -1
        :return: records. count
        """
        raise NotImplementedError()

    @abstractmethod
    async def update(self, records: Iterable[DataRecord], values: SQLValuesToWrite, returning=False) -> Union[int, Sequence[DataRecord]]:
        """
        :param records:
        :param values:
        :param returning:
        :return: return count if returning is False, otherwise records
        """
        raise NotImplementedError()

    @abstractmethod
    async def insert(self, values_lst: Iterable[SQLValuesToWrite], returning=False) -> Union[int, List[DataRecord]]:
        """
        :param values_lst:
        :param returning:
        :return: return count if returning is False, otherwise records
        """
        raise NotImplementedError()

    @abstractmethod
    async def delete(self, records: Iterable[DataRecord]) -> int:
        raise NotImplementedError()
