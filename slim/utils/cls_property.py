# code from SQLAlchemy
# Copyright 2005-2020 SQLAlchemy authors and contributors <see AUTHORS file>.
# MIT License
# https://github.com/zzzeek/sqlalchemy/blob/5881fd274015af3de37f2ff0f91ff6a7c61c1540/LICENSE


class classproperty(property):
    """A decorator that behaves like @property except that operates
    on classes rather than instances.

    The decorator is currently special when using the declarative
    module, but note that the
    :class:`~.sqlalchemy.ext.declarative.declared_attr`
    decorator should be used for this purpose with declarative.

    """

    def __init__(self, fget, *arg, **kw):
        super(classproperty, self).__init__(fget, *arg, **kw)
        self.__doc__ = fget.__doc__

    def __get__(desc, self, cls):
        return desc.fget(cls)
