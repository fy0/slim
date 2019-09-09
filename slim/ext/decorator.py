from slim.exception import SlimException
from slim.utils import async_call
from ..retcode import RETCODE
from ..base.view import BaseView, AbstractSQLView


def require_role(role=None):
    def _(func):
        async def __(view: AbstractSQLView, *args, **kwargs):
            if role not in view.roles:
                return view.finish(RETCODE.INVALID_ROLE)
            return await func(view, *args, **kwargs)
        return __
    return _


def must_be_role(role=None):
    def _(func):
        async def __(view: AbstractSQLView, *args, **kwargs):
            if role != view.current_request_role:
                return view.finish(RETCODE.INVALID_ROLE)
            return await func(view, *args, **kwargs)
        return __
    return _


async def get_ip(view: BaseView) -> bytes:
    return (await view.get_ip()).packed


def get_cooldown_decorator(aioredis_instance: object, default_unique_id_func=get_ip) -> object:
    redis = aioredis_instance

    def cooldown(interval_value_or_func, redis_key_template, *, unique_id_func=default_unique_id_func, cd_if_unsuccessed=None):
        def wrapper(func):
            async def myfunc(self: BaseView, *args, **kwargs):
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
            return myfunc
        return wrapper
    return cooldown
