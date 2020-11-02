import os
import logging
import importlib.util
import sys

logger = logging.getLogger(__name__)


def import_path(path, depth=-1):
    if depth == 0:
        return

    for base_path in sys.path:
        loaded = False
        load_path = os.path.abspath(os.path.join(base_path, path))

        if os.path.isdir(load_path) and os.path.exists(os.path.join(load_path, '__init__.py')):
            for i in os.listdir(load_path):
                fn = os.path.join(load_path, i)

                if os.path.isfile(fn):
                    if not i.startswith('_') and i.endswith('.py'):
                        modname = os.path.relpath(fn, base_path)[:-3].replace(os.path.sep, '.')
                        # modpath = os.path.abspath(fn)
                        # logger.debug('Auto load module: %s from %r' % (modname, modpath))

                        logger.info('Auto load module: %s' % (modname,))
                        importlib.import_module(modname)
                        loaded = True
                elif os.path.isdir(fn):
                    import_path(os.path.relpath(fn, base_path), depth-1)

        if loaded:
            break
