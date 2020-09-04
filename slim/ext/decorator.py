import functools
import logging
import time
from asyncio import Future
from typing import TYPE_CHECKING, Type, Union, Iterable

from schematics import Model

from slim.base.view.validate import view_validate_check
from slim.base.types.func_meta import FuncMeta
from slim.utils import async_call, get_ioloop, asyncio
from ..retcode import RETCODE

if TYPE_CHECKING:
    from ..base.view import BaseView, AbstractSQLView
    from .. import Application


logger = logging.getLogger(__name__)


def _try_create_func_meta(func):
    meta = getattr(func, '__meta__', None)
    if not meta:
        meta = FuncMeta()
        setattr(func, '__meta__', meta)
    return meta


def _decorator_fix(old_func, new_func):
    """
    使装饰器包裹函数不丢失文档信息和辅助信息
    :param old_func:
    :param new_func:
    :return:
    """
    meta = getattr(old_func, '__meta__', None)
    if isinstance(meta, FuncMeta):
        setattr(new_func, '__meta__', meta.deepcopy())
    else:
        meta = FuncMeta()
        setattr(new_func, '__meta__', meta)
    return meta


def append_validate(va_query: Type[Model] = None, va_post: Type[Model] = None, va_write_value: Type[Model] = None,
                    va_headers: Type[Model] = None):
    """
    :param va_query:
    :param va_post:
    :param va_write_value:
    :param va_headers
    :return:
    """
    def _(func):
        assert asyncio.iscoroutinefunction(func), 'Must be async function.'

        @functools.wraps(func)
        async def inner(view: 'AbstractSQLView', *args, **kwargs):
            await view_validate_check(view, va_query, va_post, va_headers, va_write_value)
            if view.is_finished: return
            return await func(view, *args, **kwargs)

        meta = _decorator_fix(func, inner)

        if va_query:
            meta.va_query_lst.append(va_query)

        if va_post:
            meta.va_post_lst.append(va_post)

        if va_write_value:
            meta.va_write_value_lst.append(va_write_value)

        return inner
    return _


def deprecated(warn_text='The interface is deprecated. We plan to remove it from yyyy-mm-dd'):
    """
    :return:
    """
    def _(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def inner(*args, **kwargs):
                logger.warning(warn_text)
                return await func(*args, **kwargs)
        else:
            @functools.wraps(func)
            def inner(*args, **kwargs):
                logger.warning(warn_text)
                return func(*args, **kwargs)

        _decorator_fix(func, inner)
        return inner
    return _


def _role_decorator(role, view_check_func):
    def _(func):
        assert asyncio.iscoroutinefunction(func), 'Must be async function.'

        @functools.wraps(func)
        async def inner(view: 'AbstractSQLView', *args, **kwargs):
            if await view_check_func(view):
                return
            return await func(view, *args, **kwargs)

        meta = _decorator_fix(inner, func)
        if isinstance(role, list):
            if meta.interface_roles is None:
                meta.interface_roles = set(role)
            else:
                for r in role:
                    meta.interface_roles.add(r)
        else:
            if meta.interface_roles is None:
                meta.interface_roles = {role}
            else:
                meta.interface_roles.add(role)
        return inner
    return _


def require_role(role: Union[str, Iterable[str]]):
    """
    Current user should have specified role
    :param role:
    :return:
    """
    async def role_check_func(view):
        if isinstance(role, str):
            if role not in view.roles:
                view.finish(RETCODE.INVALID_ROLE)
                return True
        elif isinstance(role, list):
            check = [True for i in view.roles if i in role]
            if not check:
                view.finish(RETCODE.INVALID_ROLE)
                return True
        else:
            view.finish(RETCODE.INVALID_ROLE)
            return True
    return _role_decorator(role, role_check_func)


def must_be_role(role=None):
    """
    Current user must request specified role and authorized
    :param role:
    :return:
    """
    async def role_check_func(view):
        if role != view.current_request_role:
            view.finish(RETCODE.INVALID_ROLE)
            return True

    return _role_decorator(role, role_check_func)


def timer(interval_seconds, app: 'Application', *, exit_when, loop=None):
    """
    Set up a timer
    :param app:
    :param interval_seconds:
    :param exit_when:
    :param loop:
    :return:
    """
    from ..base.app import Application
    assert isinstance(app, Application), 'app must be `Application`'

    if app.running:
        loop = loop or asyncio.get_event_loop()

    def wrapper(func):
        @functools.wraps(func)
        def runner():
            nonlocal loop
            if exit_when and exit_when():
                return

            if not loop:
                loop = loop or asyncio.get_event_loop()

            loop.call_later(interval_seconds, runner)

            if asyncio.iscoroutinefunction(func):
                asyncio.ensure_future(func())
            else:
                func()

        _decorator_fix(runner, func)
        if loop:
            loop.call_later(interval_seconds, runner)
        else:
            app._timers_before_running.append([interval_seconds, runner])
        return func

    return wrapper


async def get_ip(view: 'BaseView') -> bytes:
    return (await view.get_ip()).packed


def get_cooldown_decorator(aioredis_instance: object, default_unique_id_func=get_ip) -> object:
    redis = aioredis_instance

    def cooldown(interval_value_or_func, redis_key_template, *, unique_id_func=default_unique_id_func, cd_if_unsuccessed=None):
        def wrapper(func):
            @functools.wraps(func)
            async def myfunc(self: 'BaseView', *args, **kwargs):
                # 有可能在刚进入的时候，上一轮已经finish了，那么直接退出
                if self.is_finished: return

                unique_id = await unique_id_func(self)
                if self.is_finished: return

                if unique_id is None:
                    return await func(self, *args, **kwargs)

                key = redis_key_template % unique_id
                if await redis.get(key):
                    self.finish(RETCODE.TOO_FREQUENT, await redis.ttl(key))
                else:
                    ret = await func(self, *args, **kwargs)
                    # 如果设定了失败返回值CD （请求完成同时未成功）
                    if self.is_finished and cd_if_unsuccessed is not None:
                        if self.ret_val['code'] != RETCODE.SUCCESS:
                            await redis.set(key, '1', expire=cd_if_unsuccessed)
                            return ret

                    # 如果没有，检查是否存在豁免值
                    if self._.cancel_cooldown:
                        # 通过豁免，返回
                        return ret

                    # 检查是否使用间隔函数
                    if not isinstance(interval_value_or_func, int):
                        # 如果使用间隔函数，亦不排除直接退出的可能
                        interval = await async_call(interval_value_or_func, self, unique_id)
                        if self.is_finished: return
                    else:
                        interval = interval_value_or_func

                    # 所有跳过条件都不存在，设置正常的expire并退出
                    await redis.set(key, '1', expire=interval)
                    return ret

            _decorator_fix(func, myfunc)
            return myfunc
        return wrapper
    return cooldown


class D:
    append_validate = append_validate
    get_cooldown_decorator = get_cooldown_decorator
    must_be_role = must_be_role
    require_role = require_role
    # deprecated = deprecated
    timer = timer
