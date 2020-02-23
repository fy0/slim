from asyncio import Future
from typing import Type, TYPE_CHECKING, Set, Dict

from schematics import Model

from slim.utils.jsdict import JsDict

if TYPE_CHECKING:
    from slim.base.view import BaseView


class BeaconRouteInfo(JsDict):
    method: Set[str]  # Set[HttpMethod]
    relpath: str  # relative path
    fullpath: str
    raw: Dict


class BeaconInfo(JsDict):
    view_cls: Type['BaseView']
    name: str
    handler: Future
    handler_name: str
    route: BeaconRouteInfo

    va_query: Type[Model]
    va_post: Type[Model]
