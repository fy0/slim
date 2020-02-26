import logging

PROJECT_NAME = 'SlimApplication'
VERSION = '1.0.0'
DESC = 'A Web Application powered by slim'

HOST = '0.0.0.0'
PORT = 9999

DOC_ENABLE = True
DEBUG_LEVEL = logging.INFO
DATABASE_URI = "sqlite:///database.db"
# DATABASE_URI = "postgresql://mydb:password@localhost:5432/mydb"
# REDIS_URI = 'redis://localhost:6379'
COOKIE_SECRET = b"6aOO5ZC55LiN5pWj6ZW/5oGo77yM6Iqx5p+T5LiN6YCP5Lmh5oSB44CC"

PASSWORD_HASH_FUNC_NAME = 'sha512'
PASSWORD_HASH_ITERATIONS = 10_0000  # 默认密码迭代次数，按2017年报告推荐至少1w次

##########################################
# 加载备用配置
##########################################

try:
    import os, sys, traceback
    if os.path.exists(os.path.join(os.path.dirname(__file__), 'private.py')):
        from private import *
except ImportError as e:
    print('Load private config failed')
    traceback.print_exc()
