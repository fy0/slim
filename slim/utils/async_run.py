import sys
import asyncio

from slim.utils.win_ioloop_ctrlc_patch import ctlc_hotfix


def get_ioloop() -> asyncio.BaseEventLoop:
    loop = asyncio.get_event_loop()
    '''
    if sys.platform == 'win32' and not isinstance(loop, asyncio.ProactorEventLoop):
        loop = asyncio.ProactorEventLoop()
        ctlc_hotfix(loop)
        asyncio.set_event_loop(loop)
    '''
    return loop


def async_corun(coroutine):
    loop = get_ioloop()
    return loop.run_until_complete(coroutine)


def async_run(func):
    loop = get_ioloop()
    return loop.run_until_complete(func())


async def async_call(func, *args, **kwargs):
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    elif callable(func):
        return func(*args, **kwargs)


def sync_call(func, *args, **kwargs):
    if asyncio.iscoroutinefunction(func):
        loop = get_ioloop()
        return loop.run_until_complete(func(*args, **kwargs))
    elif callable(func):
        return func(*args, **kwargs)
