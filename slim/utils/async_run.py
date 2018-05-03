import asyncio


def async_corun(coroutine):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)


def async_run(func):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(func())


async def async_call(func, *args, **kwargs):
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    elif callable(func):
        return func(*args, **kwargs)


def sync_call(func, *args, **kwargs):
    if asyncio.iscoroutinefunction(func):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(func(*args, **kwargs))
    elif callable(func):
        return func(*args, **kwargs)

