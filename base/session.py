import json


class SimpleSession(object):
    def __init__(self, view):
        self._view = view
        self._data = self.load()

    def __delitem__(self, key):
        del self._data[key]

    def __getitem__(self, key):
        return self._data.get(key)

    def __setitem__(self, key, value):
        self._data[key] = value

    def load(self):
        _s = self._view.request.cookies.get('session') or '{}'
        #_s = self._view.request.get_cookie('session', secure=True) or '{}'
        try: _s = _s.decode('utf-8') # fix:py2
        except: pass
        return json.loads(_s)

    def flush(self):
        self._view.set_cookie('session', json.dumps(self._data), secure=True)
