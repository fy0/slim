import base64
import hashlib
import hmac
import json
import logging
from posixpath import join as urljoin


logger = logging.getLogger(__name__)
# __all__ = ('Route',)


def view_bind(app, url, view_cls):
    """
    将 API 绑定到 web 服务上
    :param view_cls: 
    :param app: 
    :param url: 
    :return: 
    """
    url = url or view_cls.__class__.__name__.lower()

    def wrap(func):
        # noinspection PyProtectedMember
        async def wfunc(request):
            view_instance = view_cls(request)
            ascii_encodable_path = request.path.encode('ascii', 'backslashreplace').decode('ascii')
            logger.info("{} {}".format(request._method, ascii_encodable_path))

            await view_instance._prepare()
            if view_instance.is_finished:
                return view_instance.response
            await view_instance.prepare()
            if view_instance.is_finished:
                return view_instance.response

            ret = await func(view_instance)
            return ret if ret is not None else view_instance.response

        return wfunc

    def add_route(route_key, item, req_handler):
        cut_uri = lambda x: x[1:] if x and x[0] == '/' else x
        if type(item) == str:
            app.router.add_route(item, urljoin('/api', cut_uri(url), cut_uri(route_key)), wrap(req_handler))
        elif type(item) == dict:
            methods = item['method']
            if type(methods) == str:
                methods = [methods]
            elif type(methods) not in (list, set, tuple):
                raise BaseException('Invalid type of route config description: %s', type(item))

            for i in methods:
                if 'url' in item:
                    app.router.add_route(i, urljoin('/api', cut_uri(url), cut_uri(item['url'])), wrap(req_handler))
                else:
                    app.router.add_route(i, urljoin('/api', cut_uri(url), cut_uri(route_key)), wrap(req_handler))
        elif type(item) in (list, set, tuple):
            for i in item:
                add_route(route_key, i, req_handler)
        else:
            raise BaseException('Invalid type of route config description: %s', type(item))

    # noinspection PyProtectedMember
    for key, http_method in view_cls._interface.items():
        request_handler = getattr(view_cls, key, None)
        if request_handler: add_route(key, http_method, request_handler)


class Route:
    urls = []

    def __call__(self, url):
        def _(cls):
            self.urls.append((url, cls))
            return cls
        return _

    def bind(self, app):
        for url, cls in self.urls:
            view_bind(app, url, cls)


try:
    # noinspection PyUnresolvedReferences
    import msgpack

    def _value_encode(obj):
        return msgpack.dumps(obj)

    def _value_decode(data: bytes):
        return msgpack.loads(data, encoding='utf-8')

except ImportError:

    def _value_encode(obj):
        return bytes(json.dumps(obj), 'utf-8')

    def _value_decode(data: bytes):
        return json.loads(str(data, 'utf-8'))


def _create_signature(secret: bytes, s):
    # hash = hashlib.blake2s(_signature_encode(s), key=secret[:32]) py3.6+
    m = hmac.new(secret, digestmod=hashlib.sha256)
    m.update(_value_encode(s))
    return m.hexdigest()


def create_signed_value(secret, s: [list, tuple]):
    sign = _create_signature(secret, s)
    return str(base64.b64encode(_value_encode(s + [sign])), 'utf-8')


def decode_signed_value(secret, s):
    s = _value_decode(base64.b64decode(bytes(s, 'utf-8')))
    data = s[:-1]
    sign = _create_signature(secret, data)
    if sign != s[-1]:
        return None
    return data
