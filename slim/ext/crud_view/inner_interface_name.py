from enum import Enum


class BuiltinCrudInterface(Enum):
    GET = 'get'
    LIST = 'list'
    LIST_PAGE = 'list_page'
    UPDATE = 'update'
    INSERT = 'insert'
    BULK_INSERT = 'bulk_insert'
    DELETE = 'delete'
