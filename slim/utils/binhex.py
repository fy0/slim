import binascii
from typing import Optional


def get_bytes_from_blob(val) -> Optional[bytes]:
    """ 不同数据库从blob拿出的数据有所差别，有的是memoryview有的是bytes """
    if isinstance(val, bytes):
        return val
    elif isinstance(val, memoryview):
        return val.tobytes()
    elif val is None:
        return None
    else:
        raise TypeError('invalid type for get bytes')


to_hex = lambda x: str(binascii.hexlify(get_bytes_from_blob(x)), 'utf-8')
to_bin = lambda x: binascii.unhexlify(bytes(x, 'utf-8'))
