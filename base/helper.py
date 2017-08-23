import logging
from posixpath import join as urljoin


logger = logging.getLogger(__name__)
__all__ = ('Route',)


def view_bind(app, url, view_cls):
    """
    将 API 绑定到 web 服务上
    :param view_cls: 
    :param app: 
    :param url: 
    :return: 
    """
    url = url or view_cls.__class__.__name__.lower()

    def wrap(url, func):
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

    def add_route(key, item, request_handler):
        cut_uri = lambda x: x[1:] if x and x[0] == '/' else x
        if type(item) == str:
            app.router.add_route(item, urljoin('/api', cut_uri(url), cut_uri(key)), wrap(url, request_handler))
        elif type(item) == dict:
            methods = item['method']
            if type(methods) == str:
                methods = [methods]
            elif type(methods) not in (list, set, tuple):
                raise BaseException('Invalid type of route config description: %s', type(item))

            for i in methods:
                if 'url' in item:
                    app.router.add_route(i, urljoin('/api', cut_uri(url), cut_uri(item['url'])), wrap(url, request_handler))
                else:
                    app.router.add_route(i, urljoin('/api', cut_uri(url), cut_uri(key)), wrap(url, request_handler))
        elif type(item) in (list, set, tuple):
            for i in item:
                add_route(key, i, request_handler)
        else:
            raise BaseException('Invalid type of route config description: %s', type(item))

    for key, http_method in view_cls._interface.items():
        request_handler = getattr(view_cls, key, None)
        if request_handler: add_route(key, http_method, request_handler)


class Route(object):
    urls = []

    def __call__(self, url):
        def _(cls):
            self.urls.append((url, cls))
            return cls
        return _

    def bind(self, app):
        for url, cls in self.urls:
            view_bind(app, url, cls)

