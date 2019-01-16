from slim.base.permission import Ability, A, DataRecord


visitor = Ability(None, {
    'example': {
        'id': (A.READ, A.QUERY),
        'state': (A.READ,),
    },
    'user': {
        'id': (A.QUERY, A.READ),
        'nickname': (A.READ,),
        'state': (A.READ,),
        'time': (A.READ,),
    }
})
