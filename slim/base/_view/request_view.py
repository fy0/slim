from .base_view import BaseView
from ..types.route_meta_info import RouteViewInfo


class RequestView(BaseView):
    @classmethod
    def cls_init(cls):
        cls._route_info = RouteViewInfo('', cls, 'Free APIs')
