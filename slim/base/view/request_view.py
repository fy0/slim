import typing

from .base_view import BaseView
from ..types.route_meta_info import RouteViewInfo
from ..web.request import ASGIRequest

if typing.TYPE_CHECKING:
    from ... import Application


class RequestView(BaseView):
    @classmethod
    def cls_init(cls):
        cls._route_info = RouteViewInfo('', cls, 'Free APIs')

    @classmethod
    async def _build(cls, app: 'Application', request: ASGIRequest, *, _hack_func=None) -> 'BaseView':
        """
        Create a sqlview, and bind request data
        :return:
        """
        if app.user_mixin_class and not issubclass(cls, app.user_mixin_class):
            class RequestUserView(cls, app.user_mixin_class):
                pass
            return await RequestUserView._build(app, request)

        return await super()._build(app, request)
