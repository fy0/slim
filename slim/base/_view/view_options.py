from typing import Type, TYPE_CHECKING

from slim.base.permission import Permissions

if TYPE_CHECKING:
    from slim.base._view.abstract_sql_view import AbstractSQLView


class ViewOptions:
    def __init__(self, *, list_page_size=20, list_accept_size_from_client=False, list_page_size_client_limit=None,
                 permission: Permissions = None):
        self.list_page_size = list_page_size
        self.list_accept_size_from_client = list_accept_size_from_client
        self.list_page_size_client_limit = list_page_size_client_limit
        if permission:
            self.permission = permission

    def assign(self, obj: Type["AbstractSQLView"]):
        obj.LIST_PAGE_SIZE = self.list_page_size
        obj.LIST_PAGE_SIZE_CLIENT_LIMIT = self.list_page_size_client_limit
        obj.LIST_ACCEPT_SIZE_FROM_CLIENT = self.list_page_size_client_limit
        if isinstance(self.permission, Permissions):
            obj.permission = self.permission
