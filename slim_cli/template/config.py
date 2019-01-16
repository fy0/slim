PROJECT_NAME = 'SlimApplication'
VERSION = '1.0.0'

HOST = '0.0.0.0'
PORT = 9999
DEBUG = True
DATABASE_URI = "sqlite:///database.db"
COOKIE_SECRET = b"6aOO5ZC55LiN5pWj6ZW/5oGo77yM6Iqx5p+T5LiN6YCP5Lmh5oSB44CC"

PASSWORD_HASH_FUNC_NAME = 'sha512'
PASSWORD_HASH_ITERATIONS = 10_0000  # 默认密码迭代次数，按2017年报告推荐至少1w次

try:
    from private import *
except ImportError:
    pass
