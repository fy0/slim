# coding:utf-8

import re
import os
import sys
from mapi.base.permission import A, Ability


class A:
    QUERY = 'query'
    READ = 'read'
    WRITE = 'write'
    CREATE = 'create'
    DELETE = 'delete'

    ALL = 'query', 'read', 'write', 'create', 'delete'


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
})


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
