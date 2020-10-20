from typing import Tuple, Type

from multidict import istr
from pycurd.crud.base_crud import BaseCrud
from pycurd.query import QueryInfo
from pycurd.types import RecordMapping
from pycurd.values import ValuesToWrite

from slim.base.view.base_view import BaseView
from slim.exception import InvalidParams, InvalidPostData


class _CrudViewUtils(BaseView):
    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小，若为-1取出所有
    LIST_PAGE_SIZE_CLIENT_LIMIT = None  # None 为与LIST_PAGE_SIZE相同，-1 为无限
    LIST_ACCEPT_SIZE_FROM_CLIENT = False  # 是否允许客户端指定 page size

    def _bulk_num(self):
        bulk_key = istr('bulk')
        if bulk_key in self.headers:
            try:
                num = int(self.headers.get(bulk_key))
                if num <= 0:
                    # num invalid
                    return 1
                return num
            except ValueError:
                pass
            return -1
        return 1

    def _get_list_page_and_size(self, page, client_size) -> Tuple[int, int]:
        page = page.strip()

        if not page.isdigit():
            raise InvalidParams("`page` is not a number")
        page = int(page)

        if self.LIST_ACCEPT_SIZE_FROM_CLIENT and client_size:
            page_size_limit = self.LIST_PAGE_SIZE_CLIENT_LIMIT or self.LIST_PAGE_SIZE
            if client_size == '-1':  # -1 means all
                client_size = -1
            elif client_size.isdigit():  # size >= 0
                client_size = int(client_size)
                if client_size == 0:
                    # use default value
                    client_size = page_size_limit
                else:
                    if page_size_limit != -1:
                        client_size = min(client_size, page_size_limit)
            else:
                raise InvalidParams("`size` is not a number")
        else:
            client_size = self.LIST_PAGE_SIZE

        return page, client_size

    async def is_returning(self) -> bool:
        return istr('returning') in self.headers

    async def _get_query_data(self):
        post = await self.post_data()
        if '$query' in post:
            return post.get('$query')
        return self.params


class CrudView(_CrudViewUtils):
    crud: BaseCrud = None
    table: Type[RecordMapping] = None

    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小，若为-1取出所有
    LIST_PAGE_SIZE_CLIENT_LIMIT = None  # None 为与LIST_PAGE_SIZE相同，-1 为无限
    LIST_ACCEPT_SIZE_FROM_CLIENT = False  # 是否允许客户端指定 page size

    is_base_class = True  # skip cls_init check

    def __init_subclass__(cls, **kwargs):
        if not cls.is_base_class:
            assert cls.crud is not None
            assert cls.table is not None

    async def get(self):
        qi = QueryInfo.from_json(self.table, await self._get_query_data())
        qi.limit = 1
        lst = await self.crud.get_list_with_foreign_keys(qi, self.crud.permission)
        if lst:
            return lst[0].to_dict()

    async def list(self):
        page, size = self._get_list_page_and_size(self.params.get('page'), self.params.get('size'))
        qi = QueryInfo.from_json(self.table, await self._get_query_data())
        qi.offset = size * (page - 1)
        qi.limit = size
        lst = await self.crud.get_list_with_foreign_keys(qi, self.crud.permission)
        return [x.to_dict() for x in lst]

    async def delete(self):
        qi = QueryInfo.from_json(self.table, await self._get_query_data())
        qi.limit = 1
        lst = await self.crud.delete_with_perm(qi, perm=self.crud.permission)
        return lst

    async def update(self):
        qi = QueryInfo.from_json(self.table, await self._get_query_data())
        qi.limit = self._bulk_num()
        values = ValuesToWrite(self.table, await self.post_data())
        lst = await self.crud.update_with_perm(qi, values, await self.is_returning(), perm=self.crud.permission)
        return lst

    async def insert(self):
        values = [ValuesToWrite(self.table, await self.post_data(), check_insert=True)]
        rtn = await self.is_returning()
        lst = await self.crud.insert_many_with_perm(self.table, values, rtn, perm=self.crud.permission)
        return lst

    async def bulk_insert(self):
        post = await self.post_data()
        if not 'items' in post:
            raise InvalidPostData("`items` is required")

        values_lst = []
        for i in post['items']:
            values_lst.append(ValuesToWrite(self.table, i, check_insert=True))

        rtn = await self.is_returning()
        lst = await self.crud.insert_many_with_perm(self.table, values_lst, rtn, perm=self.crud.permission)
        return lst
