from typing import Type, TYPE_CHECKING

if TYPE_CHECKING:
    from slim.ext.sqlview.abstract_sql_view1 import AbstractSQLView


class SQLViewOptions:
    def __init__(self, *, list_page_size=20, list_accept_size_from_client=False, list_page_size_client_limit=None):
        self.list_page_size = list_page_size
        self.list_accept_size_from_client = list_accept_size_from_client
        self.list_page_size_client_limit = list_page_size_client_limit

    def assign(self, obj: Type["AbstractSQLView"]):
        obj.LIST_PAGE_SIZE = self.list_page_size
        obj.LIST_PAGE_SIZE_CLIENT_LIMIT = self.list_page_size_client_limit
        obj.LIST_ACCEPT_SIZE_FROM_CLIENT = self.list_page_size_client_limit
