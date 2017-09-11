PROJECT_NAME = 'Slim'
VERSION = '1.0.0'

HOST = '0.0.0.0'
PORT = 9999
DEBUG = True
DATABASE_URI = "sqlite:///database.db"
COOKIE_SECRET = b"6aOO5ZC55LiN5pWj6ZW/5oGo77yM6Iqx5p+T5LiN6YCP5Lmh5oSB44CC"

try:
    from private import *
except:
    pass
