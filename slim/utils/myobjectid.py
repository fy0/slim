# coding:utf-8

import os
import sys
import time
import socket
import struct
import hashlib
import binascii

py_ver = sys.version_info.major


class ObjectID(object):
    _index = 0
    _hostname_bytes = hashlib.md5(socket.gethostname().encode('utf-8')).digest()[0:3]

    def __init__(self, object_id=None):
        if object_id:
            self._parse_id(object_id)
        else:
            self._gen_id()

    def _gen_id(self):
        # 0|1|2|3 | 4|5|6 | 7|8 | 9|10|11
        # 时间戳 | 机器  | PID | 计数器
        ObjectID._index += 1
        self.time = int(time.time())
        object_id = struct.pack(">i", self.time)
        object_id += self._hostname_bytes
        object_id += struct.pack(">H", os.getpid() % 0xFFFF)
        ObjectID._index %= 0xFFF
        object_id += struct.pack(">I", ObjectID._index)[1:]
        self.object_id = object_id

    def _parse_id(self, object_id):
        if py_ver >= 3:
            if type(object_id) == str:
                if len(object_id) != 24:
                    raise TypeError
                object_id = binascii.unhexlify(bytes(object_id, 'utf-8'))

            if type(object_id) == bytes:
                if len(object_id) != 12:
                    raise TypeError
                self.time = struct.unpack(">i", object_id[0:4])[0]
                self.object_id = object_id
            else:
                raise TypeError
        else:
            if type(object_id) != str:
                raise TypeError

            if len(object_id) == 24:
                object_id = binascii.unhexlify(object_id)

            if len(object_id) == 12:
                self.time = struct.unpack(">i", object_id[0:4])[0]
                self.object_id = object_id
            else:
                raise TypeError

    @classmethod
    def check_valid(cls, str_or_bytes):
        try:
            return ObjectID(str_or_bytes)
        except TypeError:
            pass

    def to_bin(self):
        return self.object_id

    def to_hex(self):
        return str(self)

    digest = to_bin
    hexdigest = to_hex

    def __str__(self):
        if py_ver >= 3:
            return str(binascii.hexlify(self.object_id), 'utf-8')
        else:
            return binascii.hexlify(self.object_id)

    def __repr__(self):
        return "ObjectID('%s')" % str(self)

    def __len__(self):
        return len(str(self))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.object_id == other.object_id
        raise TypeError

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return self.object_id != other.object_id
        raise TypeError

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self.object_id < other.object_id
        raise TypeError

    def __le__(self, other):
        if isinstance(other, self.__class__):
            return self.object_id <= other.object_id
        raise TypeError

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self.object_id > other.object_id
        raise TypeError

    def __ge__(self, other):
        if isinstance(other, self.__class__):
            return self.object_id >= other.object_id
        raise TypeError
