from slim.base.types.doc import ValidatorDoc


def test_create_and_read():
    doc = ValidatorDoc('qqqq', {})
    assert doc.description == 'qqqq'
    assert doc.schema == {}
