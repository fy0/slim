from dataclasses import dataclass, field
from types import FunctionType
from typing import Type, TYPE_CHECKING, Set, Optional, List

from schematics import Model

if TYPE_CHECKING:
    from slim.base.view import BaseView
    from slim.base.web.staticfile import StaticFileResponder
    from slim.base.web.ws import WebSocket


@dataclass
class RouteViewInfo:
    url: str
    view_cls: Type['BaseView']
    tag_display_name: str


@dataclass
class RouteInterfaceInfo:
    methods: List[str]
    url: str
    handler: Optional[FunctionType]

    names_exclude: Set[str]
    names_include: Set[str]
    names_varkw: Optional[str]

    summary: str = None  # 简介
    view_cls: Type['BaseView'] = None
    fullpath: str = None
    view_cls_set: Set[Type['BaseView']] = field(default_factory=lambda: set())  # plan b of clone

    va_query: Type[Model] = None
    va_post: Type[Model] = None
    va_resp: Type[Model] = None
    va_headers: Type[Model] = None
    deprecated: bool = False
    is_free_func = False

    builtin_interface: Optional[str] = None

    def clone(self):
        return RouteInterfaceInfo(**self.__dict__)

    def get_handler_name(self):
        if self.view_cls:
            return f'{self.view_cls.__name__}.{self.handler.__name__}'
        return self.handler.__name__


@dataclass
class RouteStaticsInfo:
    methods: List[str]
    url: str
    static_path: str

    fullpath: str = None
    responder: 'StaticFileResponder' = None

    def get_handler_name(self):
        return self.url


@dataclass
class RouteWebsocketInfo:
    url: str
    ws_cls: Type['WebSocket']
    fullpath: str = None
