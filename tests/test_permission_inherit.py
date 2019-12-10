from slim.base.permission import A, Ability, DataRecord, Permissions

ab1 = Ability({
    'user': {
        'username': (A.QUERY, A.READ),
        'nickname': (A.QUERY, A.READ),
        'password': (A.QUERY, A.READ),
    },
    'tab1': {A.WRITE, A.QUERY},
    '*': {A.WRITE}
})


def test_default():
    assert ab1.can_with_columns(None, A.WRITE, 'user', ['username', 'nickname', 'password', 'salt']) == {'salt'}

    assert ab1.can_with_columns(None, A.WRITE, 'tab1', {'username', 'nickname', 'password'}) == {'username', 'nickname', 'password'}
    assert ab1.can_with_columns(None, A.QUERY, 'tab1', {'username', 'nickname', 'password'}) == {'username', 'nickname', 'password'}
    assert ab1.can_with_columns(None, A.READ, 'tab1', {'username', 'nickname', 'password'}) == set()


ab2 = Ability({
    'user': {
        'username': (A.QUERY, A.READ),
        'nickname': (A.QUERY, A.READ),
        'password': (A.QUERY, A.READ),
    },
    'tab1': {A.READ},
    '|': {A.WRITE}
})


def test_overlay():
    assert ab2.can_with_columns(None, A.WRITE, 'user', ['username', 'nickname', 'password', 'salt']) == {'username', 'nickname', 'password', 'salt'}

    assert ab2.can_with_columns(None, A.READ, 'tab1', {'username', 'nickname'}) == {'username', 'nickname'}
    assert ab2.can_with_columns(None, A.WRITE, 'tab1', {'username', 'nickname'}) == {'username', 'nickname'}


ab3 = Ability({
    'user': {
        'username': (A.QUERY, A.READ),
        'nickname': (A.QUERY, A.READ),
        'password': (A.QUERY, A.READ),
    },
    '*': {A.QUERY},
    '|': {A.WRITE}
})


def test_both_default_and_overlay():
    assert ab3.can_with_columns(None, A.WRITE, 'user', ['salt']) == {'salt'}
    assert ab3.can_with_columns(None, A.QUERY, 'user', ['salt']) == {'salt'}


if __name__ == '__main__':
    test_overlay()
