from collections import OrderedDict
from .cls_init import MetaClassForInit


class StateObject(metaclass=MetaClassForInit):
    _keys = []
    _values = []
    v2k = {}
    _items = None

    @classmethod
    def keys(cls):
        return cls._keys

    @classmethod
    def values(cls):
        return cls._values

    @classmethod
    def items(cls):
        if cls._items is None:
            cls._items = []
            for k, v in zip(cls.keys(), cls.values()):
                cls._items.append((k, v),)
        return cls._items

    @classmethod
    def to_dict(cls):
        return dict(cls.items())

    @classmethod
    def cls_init(cls):
        _v2k, v2k = {}, OrderedDict()

        for k, v in cls.__dict__.items():
            if k.isupper() and type(v) == int:
                _v2k[v] = k

        for i in sorted(_v2k.keys()):
            v2k[i] = _v2k[i]

        cls._keys = list(v2k.values())
        cls._values = list(v2k.keys())
        cls.v2k = v2k


if __name__ == '__main__':
    class MyState(StateObject):
        DEL = 0
        HIDE = 10
        CLOSE = 30  # 禁止回复
        NORMAL = 50

        txt = {DEL: "删除", HIDE: "隐藏", CLOSE: "关闭", NORMAL: "正常"}

    print(list(MyState.keys()))
    print(list(MyState.values()))
    print(list(MyState.items()))
    print(list(MyState.v2k.items()))
    print([MyState.txt[x] for x in MyState.values()])
