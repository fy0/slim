import json
import requests


'''
config = {
    'remote': {
        'API_SERVER': 'http://localhost:9999',
        'WS_SERVER': 'ws://localhost:9999/ws',
        # 'authMode': 'access_token'  # access_token / access_token_in_params / cookie 可选
    },
    'request': {
        'access_token': None
    }
}
'''


class UnexpectedResponse(Exception):
    pass


class UnexpectedMethod(Exception):
    pass


def do_request(config, method, url, params=None, post_data=None, role=None):
    headers = {}
    if params is None: params = {}
    auth_mode = config['remote'].get('authMode', 'access_token')
    request_info = config.get('request', {})

    if auth_mode in ('access_token', 'access_token_in_params'):
        token = request_info.get('access_token', None)
        if auth_mode == 'access_token':
            headers['AccessToken'] = token
        else:
            params['AccessToken'] = token

    if role:
        headers['Role'] = role

    if method == 'GET':
        resp = requests.get(url, params=params, headers=headers)
    elif method == 'POST':
        resp = requests.post(url, params=params, data=post_data, headers=headers)
    else:
        resp = None

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

    def do_request(self, method, rel_path, params=None, post_data=None, role=None):
        return do_request(self.config, method, self.urlPrefix + rel_path, params=params, post_data=post_data, role=role)

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
