"""Write a PyInstaller version resource so pmtpc.exe carries product name and version metadata.

Usage: python packaging/windows/version_info.py VERSION OUT_FILE
VERSION may have a suffix (e.g. 0.1.0-dev.abc1234); the numeric fields use its X.Y.Z part.
"""

import re
import sys

TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric},
    prodvers={numeric},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Jose Cynon Luna'),
        StringStruct('FileDescription', 'Phone Mic to PC'),
        StringStruct('FileVersion', {version!r}),
        StringStruct('InternalName', 'pmtpc'),
        StringStruct('LegalCopyright', 'Copyright (C) 2026 Jose Cynon Luna. Licensed under GPL-3.0-or-later.'),
        StringStruct('OriginalFilename', 'pmtpc.exe'),
        StringStruct('ProductName', 'Phone Mic to PC'),
        StringStruct('ProductVersion', {version!r}),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"""


def numeric_version(version: str) -> tuple[int, int, int, int]:
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise SystemExit(f"version must start with X.Y.Z, got {version!r}")
    return (*map(int, match.groups()), 0)


if __name__ == "__main__":
    version, out = sys.argv[1], sys.argv[2]
    with open(out, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(version=version, numeric=numeric_version(version)))
