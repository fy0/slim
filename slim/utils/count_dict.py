import weakref


class _my_proxy(weakref.ReferenceType):
    def __getattr__(self, item):
        i = self()
        if hasattr(i, '__getattr__'):
            return i.__getattr__(item)
        else:
            return i.__getattribute__(item)


class _CountSet(set):
    def __init__(self, parent, key):
        self.key = key
        self.parent = parent
        super().__init__()

    def add(self, element):
        the_remove = super().remove

        def callback(ref):
            the_remove(ref)
            if len(self) == 0:
                del self.parent[self.key]

        super().add(_my_proxy(element, callback))

    def remove(self, element):
        raise NotImplementedError()


class CountDict(dict):
    def __setitem__(self, key, value):
        assert isinstance(value, _CountSet)
        super().__setitem__(key, value)
        value.key = key
        value.parent = self

    def __getitem__(self, key):
        if key not in self:
            self.setdefault(key, _CountSet(self, key))
        return super().__getitem__(key)
