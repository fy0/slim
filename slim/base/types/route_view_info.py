from typing import Type, TYPE_CHECKING

from slim.utils.jsdict import JsDict

if TYPE_CHECKING:
    from slim.base._view.base_view import BaseView


class RouteViewInfo(JsDict):
    url: str
    view_cls: Type['BaseView']
    tag_display_name: str

    def __init__(self, url, cls, tag_display_name=None, **kwargs):
        super().__init__(url=url, view_cls=cls, tag_display_name=tag_display_name, **kwargs)
