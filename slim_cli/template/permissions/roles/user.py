from permissions.roles.visitor import visitor
from slim.ext.permission import Ability, A

user = Ability({
    'user': {
        '|': {A.CREATE},

        'nickname': {A.READ, A.UPDATE},
        'state': {A.READ, A.UPDATE},
    },
    'example': A.ALL
}, based_on=visitor)
