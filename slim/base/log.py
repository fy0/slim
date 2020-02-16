import logging
import logging.config

"""
CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
NOTSET = 0
"""

logger = None
is_enable = False


logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True
})


def enable(level=logging.DEBUG):
    global logger, is_enable

    if not is_enable:
        default_handler = logging.StreamHandler()
        default_handler.setFormatter(logging.Formatter(
            # '[%(asctime)s][%(levelname).4s][slim] %(message)s'
            '[%(levelname).4s] %(message)s'
        ))

        logger = logging.getLogger('slim')
        logger.setLevel(level)
        logger.addHandler(default_handler)
        logger.propagate = False

        is_enable = True
