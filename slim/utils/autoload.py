import os
import logging
import importlib.util
import sys

logger = logging.getLogger(__name__)


def import_path(path, depth=-1, base_path='.'):
    # path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if depth == 0:
        return

    for i in os.listdir(os.path.join(base_path, path)):
        fn = os.path.join(base_path, path, i)

        if os.path.isfile(fn):
            if not i.startswith('_') and i.endswith('.py'):
                modname = os.path.relpath(fn, base_path)[:-3].replace(os.path.sep, '.')
                modpath = os.path.abspath(fn)

                # logger.debug('Auto load module: %s from %r' % (modname, modpath))
                logger.debug('Auto load module: %s' % (modname,))
                importlib.import_module(modname)
        elif os.path.isdir(fn):
            import_path(os.path.relpath(fn, base_path), depth-1, base_path=base_path)
