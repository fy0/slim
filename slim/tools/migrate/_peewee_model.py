import inspect
import sys
from typing import MutableSequence, MutableSet, MutableMapping, Callable

from peewee import TextField, IntegerField, BigIntegerField, BlobField, BooleanField, Field, Model
from playhouse.postgres_ext import ArrayField

from slim.utils import sentinel


def model_to_pydantic(model: Model):
    lst = model._meta.sorted_fields

    dict_ = {
        TextField: 'str',
        IntegerField: 'int',
        BigIntegerField: 'int',
        BlobField: 'bytes',
        BooleanField: 'bool',
        ArrayField: 'List'
    }

    def get_type(t):
        for k, v in dict_.items():
            if issubclass(t, k):
                return v
        return 'Any'

    print('''from pydantic import Field
from typing import Optional

from pycurd.types import RecordMapping

''')

    code = f'class {getattr(model, "__name__")}(RecordMapping):\n'
    for field in lst:
        type_ = get_type(type(field))
        code += f'\t{field.column_name}: '

        if field.null:
            code += f'Optional[{type_}]'
        else:
            code += f'{type_}'

        default = getattr(field, "default", sentinel)

        if default is not sentinel:
            if isinstance(default, (MutableSequence, MutableSet, MutableMapping)):
                code += ' = field(default_factory=lambda: %r)\n' % default
            elif isinstance(default, Callable):
                code += ' = field(default_factory=%s)\n' % default.__name__
            else:
                if not (field.null and default is None):
                    code += ' = %r\n' % default
                else:
                    code += '\n'
        else:
            code += '\n'

    return code.replace('\t', '    ')


def auto_model_to_pydantic(only_this_file=True):
    names = sys._getframe(1).f_locals
    for _, i in names.items():
        if inspect.isclass(i) and issubclass(i, Model) and getattr(i, '_meta', None):
            if only_this_file and i.__module__ != '__main__':
                continue
            print(model_to_pydantic(i))


if __name__ == '__main__':
    # usage:
    from slim.tools.migrate._peewee_model import auto_model_to_pydantic
    auto_model_to_pydantic()
