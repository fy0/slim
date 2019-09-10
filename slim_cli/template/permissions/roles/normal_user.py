from permissions.roles.visitor import visitor
from slim.base.permission import Ability, A, DataRecord


normal_user = Ability({
    'user': {
        'email': (A.CREATE,),
        'nickname': (A.READ, A.WRITE, A.CREATE),
        'state': (A.READ, A.WRITE),
    },
    'example': A.ALL
}, based_on=visitor)
