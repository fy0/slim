import os
import logging
import importlib.util


logger = logging.getLogger(__name__)


def import_path(path):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    for i in os.listdir(path):
        if not i.startswith('_') and i.endswith('.py'):
            modname = '.%s.%s' % (path, i[:-3])
            logger.debug('auto load module: "%s"' % modname)
            spec = importlib.util.spec_from_file_location(modname, os.path.join(path, i))
            foo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(foo)
