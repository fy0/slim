import asyncio


def async_corun(coroutine):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)


def async_run(func):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(func())
