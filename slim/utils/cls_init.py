# noinspection PyUnresolvedReferences
class MetaClassForInit(type):
    def __new__(mcs, *args, **kwargs):
        new_class = super().__new__(mcs, *args, **kwargs)
        if getattr(new_class, 'cls_init', None):
            new_class.cls_init()
        return new_class
