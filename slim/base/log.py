import logging

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


def enable():
    global logger, is_enable

    if not is_enable:
        default_handler = logging.StreamHandler()
        default_handler.setFormatter(logging.Formatter(
            '[%(asctime)s][%(levelname).4s][%(name)s][%(lineno)s] %(message)s'
        ))

        logger = logging.getLogger('slim')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(default_handler)

        is_enable = True
