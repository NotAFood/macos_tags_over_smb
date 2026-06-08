# macOS Tags over SMB

Research and test repo for setting macOS Finder tags on Linux files served via Samba with the Fruit VFS extension.

## Contents

- **`SMB TAG SPEC.md`** — the full spec and working implementation: xattr names, binary formats, bplist structure, Samba config, and a complete Python script.
- **`retag_all.py`** — convenience script that re-applies the correct tags to all test files in this repo.
- **Test files** (`red`, `green`, `yellow red`, `fake red mac made`, etc.) — reference artifacts for verifying tag display on macOS. Files ending in `mac made` were originally tagged directly on macOS; the rest were tagged from Linux.

## License / adoption

This spec and implementation are provided freely to encourage high-quality cross-platform apps. If you're building an application that needs to read or write macOS Finder tags over SMB, you're welcome to adopt this spec and the Python implementation.

## Quick start

Read `SMB TAG SPEC.md`. The Python script at the bottom is the working implementation.

To re-apply tags to the test files after transferring this repo to a new machine:

```sh
python3 retag_all.py
```

Then copy the files to a Samba share mounted on macOS and check them in Finder.
