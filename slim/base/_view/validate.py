from schematics.exceptions import DataError

from slim.exception import InvalidParams, InvalidPostData
from .err_catch_context import ErrorCatchContext


async def view_validate_check(view_instance, va_query, va_post):
    with ErrorCatchContext(view_instance):
        if va_query:
            try:
                # TODO: 这里有问题，对SQL请求来说，多个同名参数项，会在实际解析时会被折叠为一个数组，但是这里没有
                va_query(strict=False, validate=True, **view_instance.params)
            except DataError as e:
                raise InvalidParams(e.to_primitive())

        if va_post and view_instance.method == 'POST':
            try:
                va_post(strict=False, validate=True, **(await view_instance.post_data()))
            except DataError as e:
                raise InvalidPostData(e.to_primitive())
