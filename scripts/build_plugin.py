#!/usr/bin/env python3
"""Synchronize sandbox script copies and build a reproducible plugin ZIP."""
import argparse
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def build():
    for name in ('validate.py', 'make_import_file.py'):
        (ROOT/'rightech-plugin/skills/rightech-output/scripts'/name).write_bytes(
            (ROOT/'rightech-plugin/scripts'/name).read_bytes())
    # A local export or secret must never enter the public archive accidentally.
    tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--', 'rightech-plugin'],
                             check=True, capture_output=True).stdout
    paths = sorted(p.decode('utf-8') for p in tracked.split(b'\0') if p)
    target = ROOT/'rightech-plugin-claude.zip'
    with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in paths:
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, (ROOT/name).read_bytes())
    return target


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(build())
