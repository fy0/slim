# coding:utf-8
from slim.base.permission import A, Ability, AbilityColumn, AbilityTable, AbilityRecord


ab = Ability('normal', {
    # 测试不带通配的权限
    'user': {
        'username': ['query', 'read'],
        'nickname': ['query', 'read'],
        'password': ['query', 'read'],
    },

    # 测试白名单权限，行为应与 user 完全一致
    'account': {
        'username': ['query', 'read'],
        'nickname': ['query', 'read'],
        'password': ['query', 'read'],
        '*': [],
    },

    # 测试数据表的权限
    # 测试带通配数据表下列的权限，列权限应高于表权限
    'test': ['query', 'read', 'write', 'create', 'delete'],
    'topic': '*',
    'article': {
        'title': ['query', 'read'],
        'user': [],
        'time': '*',
        '*': '*'
    },

    # 规则测试
    'rule_test1': ['delete'],  # columns: a, b, c
    'rule_test1_1': ['delete'],  # columns: a, b, c
    'rule_test2': [],  # columns: a, b, c
})


def rule1_func1(ability, user, action, record: AbilityRecord):
    return True


def rule1_func2(ability, user, action, record: AbilityRecord):
    return True


def rule1_func3(ability, user, action, record: AbilityRecord):
    return False


ab.add_record_check([A.CREATE, A.READ], AbilityTable('rule_test1'), func=rule1_func1)
ab.add_record_check([A.WRITE], AbilityTable('rule_test1'), func=rule1_func2)
ab.add_record_check([A.DELETE], AbilityTable('rule_test1'), func=rule1_func3)


def rule2_func1(ability, user, action, record: AbilityRecord):
    return True


ab.add_record_check([A.CREATE, A.READ], AbilityColumn('rule_test2', 'a'), func=rule2_func1)
ab.add_record_check([A.CREATE, A.READ], AbilityColumn('rule_test2', 'b'), func=rule2_func1)


def test_no_wildcard():
    for t in ['user', 'account']:
        for c in ['username', 'nickname', 'password']:
            for i in ['query', 'read']:
                assert all(ab.can(None, i, (t, c)))
            for i in ['write', 'create', 'delete']:
                assert all(ab.cannot(None, i, (t, c)))

        for c in ['notexist']:
            for i in A.ALL:
                assert all(ab.cannot(None, i, (t, c)))


def test_ability_table():
    for i in A.ALL:
        assert all(ab.can(None, i, 'test'))

    for i in A.ALL:
        assert all(ab.can(None, i, 'topic'))

    for i in A.ALL:
        assert all(ab.can(None, i, 'article'))


def test_ability_column():
    for i in A.ALL:
        assert all(ab.cannot(None, i, ('article', 'user')))
    for i in (A.QUERY, A.READ):
        assert all(ab.can(None, i, ('article', 'title')))

    for i in (A.WRITE, A.CREATE, A.DELETE):
        assert all(ab.cannot(None, i, ('article', 'title')))


def test_filter():
    assert ab.can_with_columns('user', ['username', 'nickname', 'password', 'salt'], A.QUERY) == ['username', 'nickname', 'password']
    assert ab.can_with_columns('user', ['username', 'nickname', 'password', 'salt'], A.READ) == ['username', 'nickname', 'password']
    assert ab.can_with_columns('user', ['username', 'nickname', 'password', 'salt'], A.WRITE) == []
    assert ab.can_with_columns('topic', ['id', 'title', 'author'], A.WRITE) == ['id', 'title', 'author']


class DictAbilityRecord(AbilityRecord):
    def __init__(self, table_name, val: dict):
        super().__init__(table_name, val)

    def keys(self):
        return self.val.keys()

    def has(self, key):
        return key in self.val

    def get(self, key):
        return self.val.get(key)


def test_record_filter():
    record1 = DictAbilityRecord('rule_test1', {'a': 'aaa', 'b': 'bbb', 'c': 'ccc'})
    a1c = ab.can_with_columns(record1.table, record1.keys(), A.CREATE)
    a1r = ab.can_with_columns(record1.table, record1.keys(), A.READ)
    a1d = ab.can_with_columns(record1.table, record1.keys(), A.DELETE)
    assert ab.can_with_record(None, A.CREATE, record1, columns=a1c) == ['a', 'b', 'c']
    assert ab.can_with_record(None, A.READ, record1, columns=a1r) == ['a', 'b', 'c']
    assert ab.can_with_record(None, A.DELETE, record1, columns=a1d) == []
    record1_1 = DictAbilityRecord('rule_test1_1', {'a': 'aaa', 'b': 'bbb', 'c': 'ccc'})
    a1_1 = ab.can_with_columns(record1_1.table, record1_1.keys(), A.DELETE)
    assert ab.can_with_record(None, A.DELETE, record1_1, columns=a1_1) == ['a', 'b', 'c']
    assert ab.can_with_record(None, A.CREATE, record1) == ['a', 'b', 'c']
    assert ab.can_with_record(None, A.READ, record1) == ['a', 'b', 'c']
    assert ab.can_with_record(None, A.DELETE, record1) == []
    assert ab.can_with_record(None, A.DELETE, record1_1) == ['a', 'b', 'c']

    record2 = DictAbilityRecord('rule_test2', {'a': 'aaa', 'b': 'bbb', 'c': 'ccc'})
    a2r = ab.can_with_columns(record2.table, record2.keys(), A.READ)
    a2c = ab.can_with_columns(record2.table, record2.keys(), A.CREATE)
    a2d = ab.can_with_columns(record2.table, record2.keys(), A.DELETE)
    a2w = ab.can_with_columns(record2.table, record2.keys(), A.WRITE)
    assert ab.can_with_record(None, A.READ, record2, columns=a2r) == ['a', 'b']
    assert ab.can_with_record(None, A.CREATE, record2, columns=a2c) == ['a', 'b']
    assert ab.can_with_record(None, A.DELETE, record2, columns=a2d) == []
    assert ab.can_with_record(None, A.WRITE, record2, columns=a2w) == []
    
    assert ab.can_with_record(None, A.READ, record2) == ['a', 'b']
    assert ab.can_with_record(None, A.CREATE, record2) == ['a', 'b']
    assert ab.can_with_record(None, A.DELETE, record2) == []
    assert ab.can_with_record(None, A.WRITE, record2) == []


def test_global():
    pass
