from permissions.roles.visitor import visitor
from slim.base.permission import Ability, A, DataRecord


user = Ability({
    'user': {
        '|': {A.CREATE},

        'nickname': {A.READ, A.WRITE},
        'state': {A.READ, A.WRITE},
    },
    'example': A.ALL
}, based_on=visitor)
