import time
import binascii
from slim.utils import CustomID


def test_my_object_id():
    a = CustomID()
    print(a.to_hex())
    b = CustomID('5e53a2e10000000123cb6558')
    c = CustomID('5e53a2e10000000123cb6558')
    time.sleep(1)
    d = CustomID()
    e = CustomID()

    # 明确时间差距
    assert a > b
    assert a >= b
    assert a != b
    assert b < a
    assert b <= a

    # 长度与值
    assert len(a) == 24
    assert len(a.to_bin()) == 12
    assert str(binascii.hexlify(a.to_bin()), 'utf-8') == str(a)

    assert str(b) == '5e53a2e10000000123cb6558'
    assert b.to_bin() == b'^S\xa2\xe1\x00\x00\x00\x01#\xcbeX'

    # 相等
    assert a != b
    assert b == c
    assert id(b) != id(c)

    # 时间测试，相隔一秒
    assert d > a
    assert d >= a
    assert d != a
    assert a < d
    assert a <= d

    # 时间测试，紧邻创建
    assert e > d
    assert e >= d
    assert e != d
    assert d < e
    assert d <= e

    # 比较类型
    try:
        a < 1
    except Exception as e:
        assert isinstance(e, TypeError)

    try:
        a <= 1
    except Exception as e:
        assert isinstance(e, TypeError)

    try:
        a == 1
    except Exception as e:
        assert isinstance(e, TypeError)

    try:
        a != 1
    except Exception as e:
        assert isinstance(e, TypeError)

    try:
        a > 1
    except Exception as e:
        assert isinstance(e, TypeError)

    try:
        a >= 1
    except Exception as e:
        assert isinstance(e, TypeError)

    # 其他
    assert repr(a).startswith('CustomID')
    assert CustomID.check_valid(a.digest())
    assert CustomID.check_valid(a.hexdigest())
