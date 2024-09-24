import struct

def read_long(f):
    return struct.unpack('>L', f.read(4))[0]

def read_short(f):
    return struct.unpack('>H', f.read(2))[0]

def read_string(f, size):
    data = f.read(size)
    string = data.decode('utf-8').rstrip('\x00')
    return string

def read_offset_data(data, offset, size):
    return data[offset:offset + size]

def read_offset_data_long(data, offset):
    return struct.unpack('>L', data[offset:offset + 4])[0]

def read_offset_data_short(data, offset):
    return struct.unpack('>H', data[offset:offset + 2])[0]