import os
import logging
import importlib.util


logger = logging.getLogger(__name__)


def import_path(path, depth=-1):
    # path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if depth == 0:
        return

    for i in os.listdir(path):
        fn = os.path.join(path, i)

        if os.path.isfile(fn):
            if not i.startswith('_') and i.endswith('.py'):
                modname = os.path.relpath(fn)[:-3].replace(os.path.sep, '.')

                logger.debug('Auto load module: "%s"' % modname)
                importlib.import_module(modname, os.path.abspath(os.path.join(path, i)))
        elif os.path.isdir(fn):
            import_path(fn, depth-1)
