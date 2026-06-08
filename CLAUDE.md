# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A research and test repo for setting macOS Finder tags on Linux files served via Samba with the Fruit VFS extension. The primary output is the spec and the working Python implementation embedded in it.

- **`SMB TAG SPEC.md`** — the canonical reference: xattr names, binary formats, bplist structure, Samba config, and a complete working Python implementation.
- **`set_dual_tags.py`** — an earlier, incomplete approach using `setfattr` subprocess calls (broken: `setfattr` stores ASCII, not raw binary).
- **Test files** (`red`, `green`, `yellow red`, `fake red mac made`, etc.) — reference artifacts for verifying tag display on macOS. `*mac made` files were tagged directly on macOS; others were tagged from Linux.

## Key Technical Facts

**3 or 4 xattrs are required per file:**

1. `user.AFP_AfpInfo` (61 bytes) — AppleDouble stream; byte 25 = `color_id << 1` for the last color tag.
2. `user.DOSATTRIB` (24 bytes, always the same hex value) — required by Samba.
3. `user.com.apple.metadata\xef\x80\xa2_kMDItemUserTags` — primary xattr Finder reads; custom bplist00 format. The `\xef\x80\xa2` bytes are WTF-8 for U+F022 (not NBSP `\xc2\xa0` — using NBSP hides the file).
4. `user.com.apple.metadata_kMDItemUserTags` — only present when at least one color tag exists; stores a double-encoded base64 template string (not a raw bplist).

**All xattrs must be set as raw binary via `lsetxattr()` through ctypes.** `setfattr` stores values as ASCII strings, breaking DOSATTRIB and AFP parsing.

**The custom bplist format** used by the `\xef\x80\xa2` xattr is not parseable by Python's `plistlib`. The `_build_bplist()` function in the spec constructs it manually.

## Working Implementation

The correct, verified implementation is the Python script in `SMB TAG SPEC.md` (under "## Python Script"). It uses `lsetxattr()` via ctypes and handles all tag scenarios:

```
set_tags('file', 'red')                      # single color tag
set_tags('file', 'yellow', 'red')            # multiple color tags
set_tags('file', 'Important')                # text-only tag
set_tags('file', 'red', 'Important')         # color + text tag
set_tags('file', ('fake red', 'red'))        # custom name with color
```

`set_dual_tags.py` predates this and uses the broken `setfattr` approach — don't use it as a reference.

## Testing

To verify tags display correctly, copy test files to a Samba share mounted on macOS and inspect in Finder. The `getfattr -d <file>` command reads xattrs on Linux. The Samba config in the spec (vfs_objects load order, `fruit:metadata = stream`, `streams_xattr:prefix = user.`) is required for macOS to read these xattrs over SMB.
