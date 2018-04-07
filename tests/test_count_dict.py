from slim.utils.count_dict import CountDict, _CountSet


class A:
    pass


def test_count_dict1():
    cd = CountDict()
    assert isinstance(cd[1], _CountSet)
    cd = CountDict()
    assert len(cd[1]) == 0
    cd = CountDict()
    v = A()
    cd[1].add(v)
    assert len(cd[1]) == 1
    del v
    assert 1 not in cd


def test_count_dict_many():
    cd = CountDict()
    v1, v2, v3 = A(), A(), A()
    cd[1].add(v1)
    cd[1].add(v2)
    cd[1].add(v3)
    assert len(cd[1]) == 3
    del v1
    assert 1 in cd
    del v2
    assert 1 in cd
    del v3
    assert 1 not in cd
