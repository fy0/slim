from typing import Tuple, Type, Optional, Any, Union

from multidict import istr
from pycrud.crud.base_crud import BaseCrud, PermInfo
from pycrud.crud.query_result_row import QueryResultRow
from pycrud.permission import RoleDefine
from pycrud.query import QueryInfo
from pycrud.types import RecordMapping
from pycrud.values import ValuesToWrite
from slim.base.route import Route

from slim.base.view.base_view import BaseView
from slim.exception import InvalidParams, InvalidPostData
from slim.utils import get_class_full_name, pagination_calc


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
        if isinstance(page, str):
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

    async def _get_query_info(self):
        post = await self.post_data()

        if post and '$query' in post:
            data = post.get('$query')
            return QueryInfo.from_json(self.model, data, from_http_query=False)

        return QueryInfo.from_json(self.model, self.params, from_http_query=True)


class CrudView(_CrudViewUtils):
    crud: BaseCrud = None
    model: Type[RecordMapping] = None

    LIST_PAGE_SIZE = 20  # list 单次取出的默认大小，若为-1取出所有
    LIST_PAGE_SIZE_CLIENT_LIMIT = None  # None 为与LIST_PAGE_SIZE相同，-1 为无限
    LIST_ACCEPT_SIZE_FROM_CLIENT = False  # 是否允许客户端指定 page size

    is_base_class = True  # skip cls_init check

    def __init_subclass__(cls, **kwargs):
        if not cls.__dict__.get('is_base_class', False):
            assert cls.crud is not None
            assert cls.model is not None
            assert issubclass(cls.model, RecordMapping), 'cls.model must be RecordMapping: %s' % get_class_full_name(cls)

    @property
    def current_role(self) -> Optional[RoleDefine]:
        if self.crud.permission:
            return self.crud.permission.get(self.current_request_role)

    async def get_perm_info(self):
        role = self.current_role
        if not role:
            raise PermissionError("no role defined for %r" % self.current_request_role)
        return PermInfo(True, self.current_user, self.current_role)

    async def get(self):
        qi = QueryInfo.from_json(self.model, await self._get_query_data(), from_http_query=True)
        qi.limit = 1
        lst = await self.crud.get_list_with_foreign_keys(qi, perm=await self.get_perm_info())
        if lst:
            return lst[0].to_dict()

    async def list(self):
        page, size = self._get_list_page_and_size(self.params.get('page', 1), self.params.get('size', -1))
        qi = QueryInfo.from_json(self.model, await self._get_query_data(), from_http_query=True)
        qi.offset = size * (page - 1)
        qi.limit = size

        lst = await self.crud.get_list_with_foreign_keys(qi, perm=await self.get_perm_info())
        return [x.to_dict() for x in lst]

    async def list_page(self):
        page, size = self._get_list_page_and_size(self.params.get('page', 1), self.params.get('size', -1))
        qi = QueryInfo.from_json(self.model, await self._get_query_data(), from_http_query=True)
        qi.offset = size * (page - 1)
        qi.limit = size

        lst = await self.crud.get_list_with_foreign_keys(qi, with_count=True, perm=await self.get_perm_info())
        all_count = lst.rows_count

        pg = pagination_calc(all_count, size, page)
        pg['items'] = [x.to_dict() for x in lst]
        return pg

    async def delete(self):
        qi = QueryInfo.from_json(self.model, await self._get_query_data(), from_http_query=True)
        qi.limit = self._bulk_num()
        lst = await self.crud.delete_with_perm(qi, perm=await self.get_perm_info())
        return lst

    async def update(self):
        qi = QueryInfo.from_json(self.model, await self._get_query_data(), from_http_query=True)
        qi.limit = self._bulk_num()
        values = ValuesToWrite(await self.post_data(), self.model)
        lst = await self.crud.update_with_perm(qi, values, await self.is_returning(), perm=await self.get_perm_info())
        return lst

    async def insert(self) -> Optional[Union[QueryResultRow, Any]]:
        values = [ValuesToWrite(await self.post_data(), self.model, try_parse=True)]
        rtn = await self.is_returning()
        lst = await self.crud.insert_many_with_perm(self.model, values, rtn, perm=await self.get_perm_info())
        return lst[0] if lst else None

    async def bulk_insert(self):
        post = await self.post_data()
        if not 'items' in post:
            raise InvalidPostData("`items` is required")

        values_lst = []
        for i in post['items']:
            values_lst.append(ValuesToWrite(i, self.model, try_parse=True))

        rtn = await self.is_returning()
        lst = await self.crud.insert_many_with_perm(self.model, values_lst, rtn, perm=await self.get_perm_info())
        return lst

    @classmethod
    def _on_bind(cls, route: Route):
        super()._on_bind(route)

        # register interface
        route.get(summary='获取单项')(cls.get)
        route.get(summary='获取列表', url='list')(cls.list)  # /:page/:size?
        route.get(summary='获取列表(带分页)', url='list_page')(cls.list_page)
        route.post(summary='更新')(cls.update)
        route.post(summary='新建')(cls.insert)
        route.post(summary='批量新建')(cls.bulk_insert)
        route.post(summary='删除')(cls.delete)
