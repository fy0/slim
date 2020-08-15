from dataclasses import dataclass
from types import FunctionType
from typing import Type, TYPE_CHECKING, Set, Optional, List

from schematics import Model

if TYPE_CHECKING:
    from slim.base.view import BaseView


@dataclass
class RouteViewInfo:
    url: str
    view_cls: Type['BaseView']
    tag_display_name: str


@dataclass
class RouteInterfaceInfo:
    methods: List[str]
    url: str
    handler: FunctionType

    names_exclude: Set[str]
    names_include: Set[str]
    names_varkw: Optional[str]

    summary: str = None  # 简介
    view_cls: Type['BaseView'] = None
    fullpath: str = None

    va_query: Type[Model] = None
    va_post: Type[Model] = None
    va_resp: Type[Model] = None
    va_headers: Type[Model] = None
    deprecated: bool = False
    is_free_func = False
