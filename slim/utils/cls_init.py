# noinspection PyUnresolvedReferences
class MetaClassForInit(type):
    def __new__(mcs, *args, **kwargs):
        new_class = super().__new__(mcs, *args, **kwargs)
        new_class.cls_init()
        return new_class
