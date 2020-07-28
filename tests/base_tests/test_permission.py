# coding: utf-8
from typing import Set
from slim.base.permission import A, Ability, DataRecord, Permissions

ab = Ability({
    # 测试不带通配的权限
    'user': {
        'username': (A.QUERY, A.READ),
        'nickname': (A.QUERY, A.READ),
        'password': (A.QUERY, A.READ),
    },

    # 测试白名单权限，行为应与 user 完全一致
    'account': {
        'username': (A.QUERY, A.READ),
        'nickname': (A.QUERY, A.READ),
        'password': (A.QUERY, A.READ),
        '*': [],
    },

    # 测试数据表的权限
    # 测试带通配数据表下列的权限，列权限应高于表权限
    'test': A.ALL,
    'topic': '*',
    'article': {
        'title': (A.QUERY, A.READ),
        'user': [],
        'time': '*',
        '*': '*'
    },

    # 规则测试
    'rule_test1': (A.DELETE,),  # columns: a, b, c
    'rule_test1_1': (A.DELETE,),  # columns: a, b, c
    'rule_test2': [],  # columns: a, b, c
})


def rule1_func1(ability, user, action, available_columns: Set):
    available_columns.update(['a', 'b', 'c'])


def rule1_func2(ability, user, action, record: DataRecord, available_columns: Set):
    pass


def rule1_func3(ability, user, action, record: DataRecord, available_columns: Set):
    available_columns.clear()


ab.add_common_check([A.CREATE, A.READ], 'rule_test1', func=rule1_func1)
ab.add_record_check([A.WRITE], 'rule_test1', func=rule1_func2)
ab.add_record_check([A.DELETE], 'rule_test1', func=rule1_func3)


def rule2_func1(ability, user, action, available_columns: Set):
    available_columns.update(['a', 'b'])


ab.add_common_check([A.CREATE, A.READ], 'rule_test2', func=rule2_func1)


def test_no_wildcard():
    for t in ['user', 'account']:
        for c in ['username', 'nickname', 'password']:
            for i in ['query', 'read']:
                assert ab.can_with_columns(None, i, t, [c])
            for i in ['write', 'create', 'delete']:
                assert not ab.can_with_columns(None, i, t, [c])

        for c in ['notexist']:
            for i in A.ALL:
                assert not ab.can_with_columns(None, i, t, [c])


def test_ability_column():
    for i in A.ALL:
        assert not ab.can_with_columns(None, i, 'article', ['user'])
    for i in (A.QUERY, A.READ):
        assert ab.can_with_columns(None, i, 'article', ['title'])

    for i in (A.WRITE, A.CREATE, A.DELETE):
        assert not ab.can_with_columns(None, i, 'article', ['title'])


def test_filter():
    assert ab.can_with_columns(None, A.QUERY, 'user', ['username', 'nickname', 'password', 'salt']) == {'username', 'nickname', 'password'}
    assert ab.can_with_columns(None, A.READ, 'user', ['username', 'nickname', 'password', 'salt']) == {'username', 'nickname', 'password'}
    assert ab.can_with_columns(None, A.WRITE, 'user', ['username', 'nickname', 'password', 'salt']) == set()
    assert ab.can_with_columns(None, A.WRITE, 'topic', ['id', 'title', 'author']) == {'id', 'title', 'author'}


class DictDataRecord(DataRecord):
    def __init__(self, table_name, val: dict):
        super().__init__(table_name, val)

    def keys(self):
        return self.val.keys()

    def has(self, key):
        return key in self.val

    def get(self, key, default=None):
        return self.val.get(key, default)


def test_record_filter():
    record1 = DictDataRecord('rule_test1', {'a': 'aaa', 'b': 'bbb', 'c': 'ccc'})
    a1c = ab.can_with_columns(None, A.CREATE, record1.table, record1.keys())
    a1r = ab.can_with_columns(None, A.READ, record1.table, record1.keys())
    a1d = ab.can_with_columns(None, A.DELETE, record1.table, record1.keys())
    assert set(ab.can_with_record(None, A.READ, record1, available=a1r)) == {'a', 'b', 'c'}
    assert ab.can_with_record(None, A.DELETE, record1, available=a1d) == set()
    record1_1 = DictDataRecord('rule_test1_1', {'a': 'aaa', 'b': 'bbb', 'c': 'ccc'})
    a1_1 = ab.can_with_columns(None, A.DELETE, record1_1.table, record1_1.keys())
    assert set(ab.can_with_record(None, A.DELETE, record1_1, available=a1_1)) == {'a', 'b', 'c'}
    assert set(ab.can_with_record(None, A.READ, record1)) == {'a', 'b', 'c'}
    assert ab.can_with_record(None, A.DELETE, record1) == set()
    assert set(ab.can_with_record(None, A.DELETE, record1_1)) == {'a', 'b', 'c'}

    record2 = DictDataRecord('rule_test2', {'a': 'aaa', 'b': 'bbb', 'c': 'ccc'})
    a2r = ab.can_with_columns(None, A.READ, record2.table, record2.keys())
    a2c = ab.can_with_columns(None, A.CREATE, record2.table, record2.keys())
    a2d = ab.can_with_columns(None, A.DELETE, record2.table, record2.keys())
    a2w = ab.can_with_columns(None, A.WRITE, record2.table, record2.keys())
    assert set(ab.can_with_record(None, A.READ, record2, available=a2r)) == {'a', 'b'}
    assert set(a2c) == {'a', 'b'}
    assert ab.can_with_record(None, A.DELETE, record2, available=a2d) == set()
    assert ab.can_with_record(None, A.WRITE, record2, available=a2w) == set()

    assert set(ab.can_with_record(None, A.READ, record2)) == {'a', 'b'}
    assert ab.can_with_record(None, A.DELETE, record2) == set()
    assert ab.can_with_record(None, A.WRITE, record2) == set()


def test_permission_role_bug():
    p = Permissions(None)
    p.add(None, Ability({'user': {'key': (A.READ,)}}))
    p.add('user', Ability({'user': {'key': (A.READ, A.WRITE)}}))
    assert p.request_role(None, 'user') is None


def test_global():
    pass
