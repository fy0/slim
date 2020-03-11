from typing import Optional, Type

from aiohttp.web_request import BaseRequest
from schematics import Model
from schematics.exceptions import DataError

from slim.exception import InvalidParams, InvalidPostData, InvalidHeaders
from .err_catch_context import ErrorCatchContext


async def view_validate_check(view_instance, va_query: Optional[Type[Model]], va_post: Optional[Type[Model]],
                              va_headers: Optional[Type[Model]] = None):
    with ErrorCatchContext(view_instance):
        if va_query:
            try:
                # TODO: 这里有问题，对SQL请求来说，多个同名参数项，会在实际解析时会被折叠为一个数组，但是这里没有
                val = va_query(strict=False, validate=True, partial=False, raw_data=view_instance.params)
                view_instance._.validated_query = val
            except DataError as e:
                raise InvalidParams(e.to_primitive())

        if va_post and view_instance.method in BaseRequest.POST_METHODS:
            try:
                val = va_post(strict=False, validate=True, partial=False, raw_data=(await view_instance.post_data()))
                view_instance._.validated_post = val
            except DataError as e:
                raise InvalidPostData(e.to_primitive())

        if va_headers:
            try:
                val = va_headers(strict=False, validate=True, partial=False, raw_data=view_instance.headers)
                view_instance._.validated_headers = val
            except DataError as e:
                raise InvalidHeaders(e.to_primitive())
