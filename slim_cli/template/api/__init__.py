from asyncio import futures
from concurrent.futures import ThreadPoolExecutor

from slim.utils import get_ioloop

thread_executor = ThreadPoolExecutor(max_workers=4)


def run_in_thread(fn, *args, **kwargs):
    return futures.wrap_future(
        thread_executor.submit(fn, *args, **kwargs), loop=get_ioloop()
    )
