import json
import requests


'''
config = {
    'remote': {
        'API_SERVER': 'http://localhost:9999',
        'WS_SERVER': 'ws://localhost:9999/ws',
    }
}
'''


class UnexpectedResponse(Exception):
    pass


class UnexpectedMethod(Exception):
    pass


def do_request(config, method, url, params=None, post_data=None, role=None, access_token=None, *,
               request_func=requests.request):
    headers = {}
    if params is None:
        params = {}
    request_info = config.get('request', {})

    if access_token is None:
        access_token = request_info.get('access_token', None)

    headers['AccessToken'] = access_token

    if role:
        headers['Role'] = role

    resp = request_func(url, params=params, data=post_data, headers=headers)

    if resp is not None:
        if resp.status_code != 200:
            raise UnexpectedResponse("status: %d text: %r" % (resp.status_code, resp.content))
        try:
            return resp.json()
        except json.JSONDecodeError:
            raise UnexpectedResponse("status: %d text: %r" % (resp.status_code, resp.content))
    else:
        raise UnexpectedMethod(method)


class SlimViewRequest:
    def __init__(self, config, path):
        self.config = config
        self.path = path
        self.urlPrefix = "%s/api/%s" % (self.config['remote']['API_SERVER'], path)
        self.access_token = None
        self.request_func = requests.request

    def do_request(self, method, rel_path, params=None, post_data=None, role=None, access_token=None):
        access_token = access_token or self.access_token
        return do_request(self.config, method, self.urlPrefix + rel_path, params=params, post_data=post_data, role=role,
                          access_token=access_token, request_func=self.request_func)

    def get(self, params=None, role=None):
        if params and 'loadfk' in params:
            params['loadfk'] = json.loads(params['loadfk'])
        return self.do_request('GET', '/get', params, role=role)

    def list(self, params=None, page=1, size=None, role=None):
        if params and 'loadfk' in params:
            params['loadfk'] = json.loads(params['loadfk'])
        url = '/list/%s' % page
        if size: url += '/%s' % size
        return self.do_request('GET', url, params, role=role)

    def update(self, params, data, role=None):
        return self.do_request('POST', '/update', params, data, role)

    def new(self, data, role=None):
        return self.do_request('POST', '/new', {}, data, role)

    def delete(self, params, role=None):
        return self.do_request('POST', '/delete', params, None, role)
