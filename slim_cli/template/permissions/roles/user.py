from permissions.roles.visitor import visitor
from slim.ext.permission import Ability, A

user = Ability({
    'user': {
        '|': {A.CREATE},

        'nickname': {A.READ, A.WRITE},
        'state': {A.READ, A.WRITE},
    },
    'example': A.ALL
}, based_on=visitor)
