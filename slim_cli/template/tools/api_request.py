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

api_user = SlimViewRequest(config, 'user')


if __name__ == '__main__':
    pass
