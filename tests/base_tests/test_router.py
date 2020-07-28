from slim import Application, ALL_PERMISSION
from slim.base.route import Route

app = Application(cookies_secret=b'123456', permission=ALL_PERMISSION)


def test_router_simple():
    route = Route(app)
    route._bind()

