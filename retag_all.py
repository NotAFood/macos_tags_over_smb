import base64
import ctypes

libc = ctypes.CDLL("libc.so.6", use_errno=True)

COLOR_CODES = {
    'gray': 1, 'green': 2, 'purple': 3, 'blue': 4,
    'yellow': 5, 'red': 6, 'orange': 7,
}

AFP_TEMPLATE = base64.b64decode(
    'QUZQAAAAAQAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAA==')

DOSATTRIB = bytes.fromhex('00000500050000001100000020000000daf83e63b9f4dc01')

KMD_SIMPLE_TEMPLATES = {
    'gray':   b'YnBsaXN0MDChAVZncmF5ICAICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAABAA==\x00',
    'green':  b'YnBsaXN0MDChAVZncmVlbiAICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAACAA==\x00',
    'purple': b'YnBsaXN0MDChAVZwdXJwbGUICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAA==\x00',
    'blue':   b'YnBsaXN0MDChAVZCbHVlCjQICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAARAA==\x00',
    'yellow': b'YnBsaXN0MDChAVZ5ZWxsb3cICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAFAA=\x00',
    'red':    b'YnBsaXN0MDChAVVSZWQKNggKAAAAAAAAAQEAAAAAAAAAAgAAAAAAAAAAAAAAAAAAABAA\x00',
    'orange': b'YnBsaXN0MDChAVZvcmFuZ2UICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAHAA==\x00',
}

XATTR_AFP      = b'user.AFP_AfpInfo'
XATTR_DOS      = b'user.DOSATTRIB'
XATTR_KMD      = b'user.com.apple.metadata_kMDItemUserTags'
XATTR_KMD_DUAL = b'user.com.apple.metadata\xef\x80\xa2_kMDItemUserTags'

def _setxattr(path, name, value):
    ret = libc.lsetxattr(path.encode(), name, value, len(value), 0)
    if ret != 0:
        raise OSError(ctypes.get_errno(), f"lsetxattr failed on {name!r}")

def _removexattr(path, name):
    libc.lremovexattr(path.encode(), name)

def _build_bplist(tags):
    n = len(tags)
    strings = []
    for name, code in tags:
        s = name.encode('utf-8')
        if code:
            s += b'\n' + str(code).encode()
        strings.append(s)

    array_hdr = bytes([0xa0 | n]) + bytes(range(1, n + 1))
    string_offsets = []
    string_data = b''
    for s in strings:
        string_offsets.append(8 + len(array_hdr) + len(string_data))
        string_data += bytes([0x50 | len(s)]) + s

    object_section = array_hdr + string_data
    offset_table_pos = 8 + len(object_section)

    offset_table = bytes([0x08]) + bytes(string_offsets)

    num_objects = n + 1
    suffix = (b'\x00' * 6
              + b'\x01\x01'
              + b'\x00' * 7
              + bytes([num_objects])
              + b'\x00' * 15
              + bytes([offset_table_pos])
              + b'\x00')

    return b'bplist00' + object_section + offset_table + suffix

def set_tags(filename, *tag_specs):
    tags = []
    last_color_code = 0
    for spec in tag_specs:
        if isinstance(spec, tuple):
            name, color = spec
            code = COLOR_CODES[color.lower()]
        else:
            code = COLOR_CODES.get(spec.lower(), 0)
            name = spec.lower().capitalize() if code else spec
        tags.append((name, code))
        if code: last_color_code = code

    afp = bytearray(AFP_TEMPLATE)
    afp[25] = last_color_code << 1
    _setxattr(filename, XATTR_AFP, bytes(afp))
    _setxattr(filename, XATTR_DOS, DOSATTRIB)
    _setxattr(filename, XATTR_KMD_DUAL, _build_bplist(tags))

    last_color_name = next(
        (c for c, v in COLOR_CODES.items() if v == last_color_code), None)
    if last_color_name and last_color_name in KMD_SIMPLE_TEMPLATES:
        _setxattr(filename, XATTR_KMD, KMD_SIMPLE_TEMPLATES[last_color_name])
    else:
        _removexattr(filename, XATTR_KMD)

    print(f"Tagged '{filename}': {tag_specs}")


import os
os.chdir('/home/cael/Repos/macos_tags_over_smb')

set_tags('red', 'red')
set_tags('green', 'green')
set_tags('yellow', 'yellow')
set_tags('blue', 'blue')
set_tags('orange', 'orange')
set_tags('purple', 'purple')
set_tags('gray', 'gray')
set_tags('yellow red', 'yellow', 'red')
set_tags('yellow red mac made', 'yellow', 'red')
set_tags('purple blue', 'purple', 'blue')
set_tags('fake red', ('fake red', 'red'))
set_tags('fake red mac made', ('fake red', 'red'))
set_tags('important', 'Important')
set_tags('important mac made', 'Important')
