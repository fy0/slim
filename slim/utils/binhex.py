import binascii

to_hex = lambda x: str(binascii.hexlify(x), 'utf-8')
to_bin = lambda x: binascii.unhexlify(bytes(x, 'utf-8'))
