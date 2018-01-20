import os
import time
import socket
import struct
import hashlib
import binascii


class CustomID(object):
    _cache_index = None
    _cache_time = None
    _cache_time_float = None

    _index = 0
    _hostname_bytes = hashlib.md5(socket.gethostname().encode('utf-8')).digest()[:2]

    def __init__(self, custom_id=None):
        if custom_id:
            self._parse_id(custom_id)
        else:
            self._gen_id()

    def _gen_id(self):
        # 0|1|2|3  |   4|5|6|7   |   7|8   | 9|10
        # 时间戳  |    计数器   |   机器  |  PID
        cls = self.__class__
        cls._index += 1
        cls._index %= 0xFFFFFFFF # 安全阈值：每 1s 2^32 -1 个
        time_float = time.time()
        self._time = int(time_float)

        # 防止重复
        if self._time == cls._cache_time:
            if cls._index + 1 == cls._cache_index:
                offset = self.time - self._cache_time_float + 1.1
                time.sleep(offset)
        else:
            cls._cache_index = cls._index
            cls._cache_time = self.time
            cls._cache_time_float = time_float

        _1 = self._time.to_bytes(4, 'big')
        _2 = cls._index.to_bytes(4, 'big')
        _3 = self._hostname_bytes
        _4 = (os.getpid() % 0xFFFF).to_bytes(2, 'big')
        self._id = b''.join((_1, _2, _3, _4),)

    @property
    def time(self):
        return self._time

    def _parse_id(self, custom_id):
        if type(custom_id) == str:
            if len(custom_id) != 24:
                raise TypeError
            custom_id = binascii.unhexlify(bytes(custom_id, 'utf-8'))

        if type(custom_id) == bytes:
            if len(custom_id) != 12:
                raise TypeError
            self._time = int.from_bytes(custom_id[:4], 'big')
            self._id = custom_id
        else:
            raise TypeError

    @classmethod
    def check_valid(cls, str_or_bytes):
        try:
            return cls(str_or_bytes)
        except TypeError:
            pass

    def to_bin(self):
        return self._id

    def to_hex(self):
        return str(self)

    digest = to_bin
    hexdigest = to_hex

    def __str__(self):
        return str(binascii.hexlify(self._id), 'utf-8')

    def __repr__(self):
        return "CustomID('%s')" % str(self)

    def __len__(self):
        return len(str(self))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._id == other._id
        raise TypeError

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return self._id != other._id
        raise TypeError

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self._id < other._id
        raise TypeError

    def __le__(self, other):
        if isinstance(other, self.__class__):
            return self._id <= other._id
        raise TypeError

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self._id > other._id
        raise TypeError

    def __ge__(self, other):
        if isinstance(other, self.__class__):
            return self._id >= other._id
        raise TypeError
