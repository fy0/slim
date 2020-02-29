# coding:utf-8
from copy import deepcopy as _deepcopy


class JsDict(dict):
    def __getitem__(self, item):
        return self.get(item)

    def __repr__(self):
        return '<jsDict %s>' % dict.__repr__(self)

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    __getattr__ = __getitem__

    def deepcopy(self):
        return JsDict(_deepcopy(dict(self)))
