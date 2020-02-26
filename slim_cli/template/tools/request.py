from slim.tools.request import SlimViewRequest

config = {
    'remote': {
        'API_SERVER': 'http://localhost:9999',
        'WS_SERVER': 'ws://localhost:9999/ws'
    },
    'request': {
        'access_token': None
    }
}

try:
    import os, sys, traceback
    if os.path.exists(os.path.join(os.path.dirname(__file__), 'private.py')):
        from private import *

except ImportError as e:
    print('Load private config failed')
    traceback.print_exc()


class UserViewRequest(SlimViewRequest):
    def signin(self, username, password):
        resp = self.do_request('POST', '/signin', post_data={'username': username, 'password': password}, role=None)
        assert resp['code'] == 0, resp
        config['request']['access_token'] = resp['data']['access_token']
        return resp

    def signup(self, username, password):
        resp = self.do_request('POST', '/signup', post_data={'username': username, 'password': password}, role=None)
        assert resp['code'] == 0, resp
        config['request']['access_token'] = resp['data']['access_token']
        return resp


api_user = SlimViewRequest(config, 'user')


if __name__ == '__main__':
    pass
