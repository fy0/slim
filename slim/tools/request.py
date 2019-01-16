# >= python3.6 only
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


def do_request(config, method, url, params=None, data=None, role=None):
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
        resp = requests.post(url, params=params, data=data)
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

    def get(self, params=None, role=None):
        if params and 'loadfk' in params:
            params['loadfk'] = json.loads(params['loadfk'])
        return do_request(self.config, 'GET', self.urlPrefix + '/get', params, role=role)

    def list(self, params=None, page=1, size=None, role=None):
        if params and 'loadfk' in params:
            params['loadfk'] = json.loads(params['loadfk'])
        url = self.urlPrefix + '/list/%s' % page
        if size: url += '/%s' % size
        return do_request(self.config, 'GET', url, params, role=role)

    def update(self, params, data, role=None):
        return do_request(self.config, 'POST', self.urlPrefix + '/update', params, data, role)

    def new(self, data, role=None):
        return do_request(self.config, 'POST', self.urlPrefix + '/new', {}, data, role)

    def delete(self, params, role=None):
        return do_request(self.config, 'POST', self.urlPrefix + '/delete', params, {}, role)
