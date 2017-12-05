import time
import base64
from http.cookiejar import CookieJar

from requests.cookies import morsel_to_cookie, merge_cookies
from requests.utils import dict_from_cookiejar

from slim import app_init
from slim.base.helper import create_signed_value, decode_signed_value, _value_decode, _value_encode, Route
from slim.base.view import BaseView
from slim.retcode import RETCODE

secret = b'asdasd' * 5


def test_sign():
    timestamp = int(time.clock())
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


route = Route()
app = app_init(cookies_secret=secret, route=route)


class FakeRequest:
    app = app
    cookies = {}


@route('/')
class CookiesView(BaseView):
    pass


cookies_view = CookiesView(FakeRequest())


def test_app_secure_cookies():
    cookies_view.set_secure_cookie('test', '内容测试')
    cookies_view.set_secure_cookie('test2', {'value': '内容测试'})
    cookies_view.finish(RETCODE.SUCCESS)

    cookies_jar = CookieJar()
    for k, v in cookies_view.response.cookies.items():
        cookies_jar.set_cookie(morsel_to_cookie(v))

    cookies_view.request.cookies = dict_from_cookiejar(cookies_jar)

    assert cookies_view.get_secure_cookie('test') == '内容测试'
    assert cookies_view.get_secure_cookie('test2') == {'value': '内容测试'}
