from slim.base.permission import A, Ability, DataRecord

visitor = Ability(None, {
    'test': {
        'id': (A.QUERY, A.READ),
        'test': (A.READ,),
    },
    'pics': A.ALL
})

normal_user = Ability('user', {
    'test': {
        'id': (A.QUERY, A.READ, A.CREATE, A.DELETE),
        'test': (A.READ, A.WRITE, A.CREATE, A.DELETE),
    },
}, based_on=visitor)
