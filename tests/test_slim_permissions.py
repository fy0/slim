from slim.base.app import SlimPermissions

flag = 'TeSt.'


def test_slim_permissions():
    o = SlimPermissions(flag)
    assert o.aaa == flag
    assert o['aaa'] == flag

    o.aaa = '123'
    assert o.aaa == '123'
    assert o['aaa'] == '123'
