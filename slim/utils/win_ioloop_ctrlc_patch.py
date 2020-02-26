# https://gist.github.com/lambdalisue/05d5654bd1ec04992ad316d50924137c

import asyncio
import sys

# Ctrl-C (KeyboardInterrupt) does not work well on Windows
# This module solve that issue with wakeup coroutine.
# https://stackoverflow.com/questions/24774980/why-cant-i-catch-sigint-when-asyncio-event-loop-is-running/24775107#24775107

if sys.platform.startswith('win'):
    def ctlc_hotfix(loop: asyncio.AbstractEventLoop) -> asyncio.AbstractEventLoop:
        loop.call_soon(_wakeup, loop, 1.0)
        return loop

    def _wakeup(loop: asyncio.AbstractEventLoop, delay: float=1.0) -> None:
        loop.call_later(delay, _wakeup, loop, delay)
else:
    # Do Nothing on non Windows
    def ctlc_hotfix(loop: asyncio.AbstractEventLoop) -> asyncio.AbstractEventLoop:
        return loop
