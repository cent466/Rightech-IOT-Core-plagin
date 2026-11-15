#!/usr/bin/env python3
"""Synchronize sandbox script copies and build a reproducible plugin ZIP."""
import argparse
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SHARED_SCRIPTS = ('validate.py', 'make_import_file.py', 'model_tools.py', 'validate_svg.py',
                  'draw_svg.py', 'render_svg.py', 'replay_cases.py')
SHARED_RESOURCES = ('requirements-tools.txt', 'schemas/cases.schema.json', 'schemas/drawing.schema.json',
                    'references/model-tools.md', 'examples/model-tools/model.json', 'examples/model-tools/cases.json',
                    'examples/model-tools/drawings/temperature.json', 'examples/model-tools/drawings/humidity.json',
                    'examples/model-tools/icons/temperature.svg', 'examples/model-tools/icons/humidity.svg',
                    'examples/model-tools/icons/online.svg', 'examples/model-tools/icons/serial.svg',
                    'examples/model-tools/icons/channel.svg')


def build():
    for name in SHARED_SCRIPTS:
        (ROOT/'rightech-plugin/skills/rightech-output/scripts'/name).write_bytes(
            (ROOT/'rightech-plugin/scripts'/name).read_bytes())
    for name in SHARED_RESOURCES:
        target = ROOT/'rightech-plugin/skills/rightech-output'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/'rightech-plugin'/name).read_bytes())
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
