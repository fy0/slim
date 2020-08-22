import time
import base64
from http.cookiejar import CookieJar

from requests.cookies import morsel_to_cookie
from requests.utils import dict_from_cookiejar

from slim import Application, ALL_PERMISSION
from slim.base.helper import create_signed_value, decode_signed_value, _value_decode, _value_encode
from slim.base.view import BaseView
from slim.retcode import RETCODE

secret = b'asdasd' * 5


def test_sign():
    timestamp = int(time.process_time())
    to_sign = [1, timestamp, 'test name', 'test value 中文', {'asd': '测试'}]
    value = create_signed_value(secret, to_sign)

    decode_data = decode_signed_value(secret, value)
    assert decode_data == to_sign

    # 篡改数据测试
    s = _value_decode(base64.b64decode(bytes(value, 'utf-8')))
    s[3] = 'test value'
    val_changed = str(base64.b64encode(_value_encode(s)), 'utf-8')

    decode_data = decode_signed_value(secret, val_changed)
    assert decode_data is None


def test_app_secure_cookies():
    app = Application(cookies_secret=secret, permission=ALL_PERMISSION)
    cookies_view = BaseView(app)
    cookies_view.set_secure_cookie('test', '内容测试')
    cookies_view.set_secure_cookie('test2', {'value': '内容测试'})
    cookies_view.finish(RETCODE.SUCCESS)

    class CookieDict(dict):
        @property
        def key(self):
            return self['name']

        @property
        def value(self):
            return self['value']

        def __getitem__(self, key):
            try:
                return super().__getitem__(key)
            except KeyError:
                return ''

    cookies_jar = CookieJar()
    for k, v in cookies_view.response.cookies.items():
        cookies_jar.set_cookie(morsel_to_cookie(CookieDict(v)))

    cookies_view._cookies_cache = dict_from_cookiejar(cookies_jar)

    assert cookies_view.get_secure_cookie('test') == '内容测试'
    assert cookies_view.get_secure_cookie('test2') == {'value': '内容测试'}
