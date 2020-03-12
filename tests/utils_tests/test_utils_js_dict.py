from slim.utils.jsdict import JsDict

flag = 'TeSt.'


def test_js_dict():
    o = JsDict()
    o.aaa = flag
    assert o['aaa'] == flag

    o.aaa = '123'
    assert o.aaa == '123'
    assert o['aaa'] == '123'


def test_js_dict_repr():
    d = {'a': 1}
    a = JsDict(d)
    assert repr(a) == "<jsDict {'a': 1}>"

