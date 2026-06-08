# macOS Finder Tags via Samba/Fruit VFS

How to create macOS Finder tag colors from Linux on a Samba share mounted with the Fruit VFS extension.

## Tag Types

macOS Finder supports two kinds of tags:

- **Color tags** — one of the 7 built-in colors, shown as a colored dot. The tag name is the color name.
- **Text tags** — arbitrary label with no color dot (e.g. "Important", "Work", "Review").

Both types use the same xattr structure; the difference is in the bplist encoding and AFP color byte.

## Tag Color Codes

| Color  | Code |
|--------|------|
| Gray   | 1    |
| Green  | 2    |
| Purple | 3    |
| Blue   | 4    |
| Yellow | 5    |
| Red    | 6    |
| Orange | 7    |

Text-only tags have **no color code** — their AFP byte 25 is `0x00` and their bplist string has no `\n<digit>` suffix.

---

## Required Extended Attributes

A file needs **3 xattrs** to display a single tag on macOS, and **4 xattrs** for multiple tags.

> **Critical**: All xattr values must be set as **raw binary bytes** via the kernel syscall.
> Using `setfattr -v` stores the value as a literal string, which breaks DOSATTRIB and makes files appear hidden on macOS.
> Always use `lsetxattr()` directly (see the Python script below).

---

### 1. `user.AFP_AfpInfo` (61 bytes)

AppleDouble metadata stream. FinderInfo occupies bytes 16–47. The legacy label color is at **byte 25** (FinderInfo byte 9), encoded as `color_id << 1`:

| Color  | Code | AFP byte 25 |
|--------|------|-------------|
| Gray   | 1    | 0x02        |
| Green  | 2    | 0x04        |
| Purple | 3    | 0x06        |
| Blue   | 4    | 0x08        |
| Yellow | 5    | 0x0A        |
| Red    | 6    | 0x0C        |
| Orange | 7    | 0x0E        |

Base template (61 bytes, base64). Byte 25 is `0x00` — set it to `color_id << 1`:
```
QUZQAAAAAQAAAAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAA==
```

For **multiple tags**, set byte 25 to the color of the **last color tag** in the list.
For **text-only tags** (no color), set byte 25 to `0x00`.

---

### 2. `user.DOSATTRIB` (24 bytes, raw binary)

DOS file attributes stream required by Samba. Raw binary value (hex):
```
00000500050000001100000020000000daf83e63b9f4dc01
```

This value is the same regardless of tag color. **Must be stored as raw bytes** — not as a base64 string.

---

### 3. `user.com.apple.metadata_kMDItemUserTags` *(Linux-created files)*

Binary plist (`bplist00`) array of tag strings, each formatted as `"Name\nColorCode"`.

For a single tag this is the only kMDItemUserTags xattr needed. For multiple tags, see §4.

> **Note**: Files tagged directly on macOS only have the `\xef\x80\xa2`-separated xattr (§4), not this one. Linux-created files need this xattr for single tags. Both are present when multiple tags are set from Linux.

Single-tag bplist templates (base64) — verified from real files:

| Color  | Base64 value |
|--------|--------------|
| Gray   | `YnBsaXN0MDChAVZncmF5ICAICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAABAA==` |
| Green  | `YnBsaXN0MDChAVZncmVlbiAICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAACAA==` |
| Purple | `YnBsaXN0MDChAVZwdXJwbGUICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAADAA==` |
| Blue   | `YnBsaXN0MDChAVZCbHVlCjQICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAARAA==` |
| Yellow | `YnBsaXN0MDChAVZ5ZWxsb3cICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAFAA==` |
| Red    | `YnBsaXN0MDChAVVSZWQKNggKAAAAAAAAAQEAAAAAAAAAAgAAAAAAAAAAAAAAAAAAABAA` |
| Orange | `YnBsaXN0MDChAVZvcmFuZ2UICgAAAAAAAAEBAAAAAAAAAAIAAAAAAAAAAAAAAAAAAAAHAA==` |

> The bplist format used by macOS for single tags is **not** parseable by Python's `plistlib` — it uses a non-standard variant. Use the templates above for color tags, or the builder function in the script for arbitrary text tags.

---

### 4. `user.com.apple.metadata\xef\x80\xa2_kMDItemUserTags` *(primary tag xattr)*

The **primary** kMDItemUserTags xattr that Finder actually reads. Present on all tagged files — both Mac-created and Linux-created.

The xattr name contains the byte sequence `\xef\x80\xa2` between `metadata` and `_kMDItemUserTags`. This is the WTF-8 encoding of a private-use Unicode code point (U+F022), **not** UTF-8 non-breaking space (`\xc2\xa0` / U+00A0). Using `\xc2\xa0` produces files that are hidden on macOS with only one tag visible.

The value is a custom binary plist (`bplist00`) encoding an array of tag strings. Each string is:
- **Color tag**: `"Name\nN"` where N is the color code digit (e.g. `"Yellow\n5"`)
- **Text tag**: `"Name"` with no suffix (e.g. `"Important"`)

The bplist uses a non-standard format that `plistlib` cannot parse. See **Bplist Format** below.

This xattr **cannot** be set with `setfattr` due to the non-UTF-8 name bytes. Use `lsetxattr()` via ctypes.

---

## Bplist Format

The `\xef\x80\xa2` xattr uses a custom bplist variant that `plistlib` cannot parse or generate. Structure:

```
62706c6973743030               bplist00 magic (8 bytes)
a1 01                          array of 1 item  (a2 01 02 for 2 items, etc.)
5L name_bytes [0a digit]       string object: 5L = length marker, then UTF-8 bytes
                               color tags append \n + digit; text tags stop after name
08                             offset table marker
[string offset bytes...]       one byte per string: file offset of its 5L byte
                               (array's own offset is NOT included)
00 00 00 00 00 00 01 01        fixed header fields
00 00 00 00 00 00 00 NN        NN = total object count (1 array + N strings)
00 00 00 00 00 00 00           padding
00 00 00 00 00 00 00 00        padding
TT 00                          TT = file offset of the 08 marker; final null
```

**Tag string length marker (`5L`):** L is the total byte length of the string including `\n` and digit.
- `"Yellow\n5"` = 8 bytes → `58`
- `"Red\n6"` = 5 bytes → `55`
- `"Purple\n3"` = 8 bytes → `58`... wait, Purple is 6+2=8 → `58`
- `"Important"` = 9 bytes → `59`

The builder function in the script constructs this format exactly for any combination of color and text tags, verified byte-identical against macOS Finder output.

---

## Python Script

Sets one or more tags on a file. Supports color tags, text tags, and combinations.
Uses `lsetxattr()` throughout to ensure all values are stored as raw binary.

```python
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

# Verified single-color bplist templates (base64). Used as the simple xattr value.
# macOS writes these as double-encoded strings (base64 text stored as xattr bytes).
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
    """Build the custom bplist00 format macOS uses for kMDItemUserTags.

    tags: list of (name, color_code) tuples. color_code=0 for text-only tags.
    Verified to produce byte-identical output to macOS Finder for all tested cases.
    """
    n = len(tags)
    strings = []
    for name, code in tags:
        s = name.encode('utf-8')
        if code:
            s += b'\n' + str(code).encode()
        strings.append(s)

    # Object section: array header (aN + item refs) then string objects
    array_hdr = bytes([0xa0 | n]) + bytes(range(1, n + 1))
    string_offsets = []
    string_data = b''
    for s in strings:
        string_offsets.append(8 + len(array_hdr) + len(string_data))
        string_data += bytes([0x50 | len(s)]) + s

    object_section = array_hdr + string_data
    offset_table_pos = 8 + len(object_section)

    # Offset table: 0x08 marker + one byte per string offset (no array offset)
    offset_table = bytes([0x08]) + bytes(string_offsets)

    # Fixed-format suffix (observed from macOS output):
    #   6 zero bytes, 0x01 0x01, 7 zero bytes, num_objects,
    #   15 zero bytes, offset_table_pos, 0x00
    num_objects = n + 1  # array object + n string objects
    suffix = (b'\x00' * 6
              + b'\x01\x01'
              + b'\x00' * 7
              + bytes([num_objects])
              + b'\x00' * 15
              + bytes([offset_table_pos])
              + b'\x00')

    return b'bplist00' + object_section + offset_table + suffix

def set_tags(filename, *tag_specs):
    """Set tags on a file.

    tag_specs: color name strings, arbitrary text strings, or (name, color) tuples.
      - 'red'                  built-in Red color tag
      - 'yellow', 'red'        two color tags
      - 'Important'            text-only tag (no color dot)
      - ('fake red', 'red')    arbitrary name with red color assigned
      - 'green', ('todo', 'blue')  mixed
    """
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

    # AFP_AfpInfo: byte 25 = last color tag's color_id << 1 (0 if no color tags)
    afp = bytearray(AFP_TEMPLATE)
    afp[25] = last_color_code << 1
    _setxattr(filename, XATTR_AFP, bytes(afp))

    # DOSATTRIB: always the same
    _setxattr(filename, XATTR_DOS, DOSATTRIB)

    # Primary bplist — all tags
    _setxattr(filename, XATTR_KMD_DUAL, _build_bplist(tags))

    # Simple xattr: double-encoded template matching the last color tag
    # (macOS writes this; content doesn't need to match the actual tags)
    last_color_name = next(
        (c for c, v in COLOR_CODES.items() if v == last_color_code), None)
    if last_color_name and last_color_name in KMD_SIMPLE_TEMPLATES:
        _setxattr(filename, XATTR_KMD, KMD_SIMPLE_TEMPLATES[last_color_name])
    else:
        _removexattr(filename, XATTR_KMD)

    print(f"Tagged '{filename}': {tag_specs}")


# Usage
set_tags('myfile.txt', 'green')
set_tags('myfile.txt', 'yellow', 'red')
set_tags('myfile.txt', 'Important')
set_tags('myfile.txt', 'red', 'Important')
set_tags('myfile.txt', ('fake red', 'red'))
```

---

## Technical Details

### AFP_AfpInfo Structure (61 bytes)

| Offset | Size | Field                          |
|--------|------|--------------------------------|
| 0      | 4    | Signature `AFP\0`              |
| 4      | 4    | Version (`0x00000100`)         |
| 8      | 4    | Reserved                       |
| 12     | 4    | Backup time                    |
| 16     | 32   | FinderInfo (label color at [9])|
| 48     | 6    | ProDosInfo                     |
| 54     | 7    | Reserved                       |

Decode label color: `color_id = (AFP_AfpInfo[25] & 0x0E) >> 1`

### Why All Xattrs Must Be Raw Binary

`setfattr -v <string>` stores the literal bytes of whatever string you pass. If you pass a base64 string, it stores the ASCII characters of that base64 string — **not** the decoded binary data. This affects every xattr:

- **DOSATTRIB**: stored as ASCII → Samba misreads attribute flags → macOS hides the file
- **AFP_AfpInfo**: stored as ASCII → FinderInfo unreadable → tag color not displayed
- **kMDItemUserTags**: stored as ASCII → Finder can't parse the plist → no tag shown

Always use `lsetxattr()` via ctypes (as in the script above) to store raw binary values. `setfattr` is only safe for human-readable string xattrs.

### Dual-Tag Xattr Name Encoding

macOS uses the byte sequence `\xef\x80\xa2` as the separator in the second kMDItemUserTags xattr name. This is the WTF-8 / CESU-8 encoding of a private-use Unicode code point (U+F022), **not** the UTF-8 non-breaking space (`\xc2\xa0` / U+00A0). Using `\xc2\xa0` produces a file that is hidden on macOS with only one tag visible.

Because this byte sequence is not valid UTF-8, it cannot be expressed in a Python string or passed to `setfattr`. It must be set using the raw bytes interface: `lsetxattr()` via ctypes.

### Tag Scenarios

| Scenario                    | AFP[25]          | `metadata_kMD` (simple)          | `metadata\xef\x80\xa2_kMD` (dual)       |
|-----------------------------|------------------|----------------------------------|------------------------------------------|
| Single color tag            | `color_id << 1`  | double-encoded template          | custom bplist: `["Name\nN"]`             |
| Multiple color tags         | last color `<< 1`| double-encoded last color        | custom bplist: `["Name\nN", ...]`        |
| Text-only tag               | `0x00`           | omitted                          | custom bplist: `["Label"]`               |
| Color + text tag            | color `<< 1`     | double-encoded color template    | custom bplist: `["Color\nN", "Label"]`   |
| Named tag with color        | `color_id << 1`  | double-encoded matching template | custom bplist: `["custom name\nN"]`      |

**Named tags with color** (e.g. a tag literally named "fake red" but colored red) use the same bplist format as color tags — the string is `"name\ncolor_code"` regardless of whether the name matches the color. The AFP color byte and simple template both reflect the assigned color, not the name.

The `\xef\x80\xa2` xattr is present on **all** tagged files — it is the primary xattr Finder reads.
The simple `metadata_kMD` xattr is only present when at least one tag has a color; macOS writes it as a double-encoded base64 string (not a raw bplist). Its content reflects the last color tag's color, regardless of the actual tag names.

---

## Working Samba Configuration

Verified working on Ubuntu with macOS client.

### Global Settings

```ini
[global]
   server min protocol = SMB3
   ea support = yes

   vfs objects = catia fruit streams_xattr
   fruit:aapl = yes
   fruit:metadata = stream
   fruit:model = MacSamba
   fruit:nfs_aces = no
   fruit:copyfile = yes
   fruit:zero_file_id = yes
   fruit:delete_empty_adfiles = yes
   fruit:wipe_intentionally_left_blank_rfork = yes

   streams_xattr:prefix = user.
   streams_xattr:store_stream_type = no
```

### Share Settings

```ini
[sharename]
   path = /home/cael
   valid users = cael
   read only = no
   vfs objects = catia fruit streams_xattr
   fruit:metadata = stream
   fruit:copyfile = yes
```

### Key Settings

| Setting                          | Value                      | Why                                                        |
|----------------------------------|----------------------------|------------------------------------------------------------|
| `fruit:metadata`                 | `stream`                   | Stores metadata via streams_xattr with `user.` prefix      |
| `streams_xattr:prefix`           | `user.`                    | Maps SMB stream `name:$DATA` → Linux xattr `user.name`     |
| `streams_xattr:store_stream_type`| `no`                       | Omits `:$DATA` suffix from xattr name                      |
| `ea support`                     | `yes`                      | Enables extended attributes on the Linux filesystem        |
| `vfs objects`                    | `catia fruit streams_xattr`| Required load order                                        |

---

## References

- [Samba vfs_fruit.c](https://github.com/samba-team/samba/blob/51cdf8f538dfd7af82c94bff9acaefbd238ff66a/source3/modules/vfs_fruit.c)
- [Samba MacExtensions.h — AFP_AfpInfo structure](https://github.com/samba-team/samba/blob/51cdf8f538dfd7af82c94bff9acaefbd238ff66a/source3/include/MacExtensions.h)
- [osxmetadata — tag color constants](https://github.com/RhetTbull/osxmetadata/blob/a4f3b71ef0873c82c4345ab82aa6c613d7f70c3e/osxmetadata/constants.py)
- [osxmetadata — FinderInfo color bit offset](https://github.com/RhetTbull/osxmetadata/blob/a4f3b71ef0873c82c4345ab82aa6c613d7f70c3e/osxmetadata/finder_info.py)
