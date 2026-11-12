#!/usr/bin/env python3
"""Install two pinned wheels into an isolated host-only test directory."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'tests/haptics-emulator-dependencies.json'
DEST = ROOT / 'tools/haptics-emulator-python'


def main():
    packages = json.loads(LOCK.read_text())
    DEST.mkdir(parents=True, exist_ok=True)
    for package in packages:
        with urllib.request.urlopen(package['url'], timeout=45) as response:
            data = response.read()
        assert hashlib.sha256(data).hexdigest() == package['sha256'], package['package']
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for item in archive.infolist():
                target = (DEST / item.filename).resolve()
                assert target.is_relative_to(DEST.resolve()), item.filename
            archive.extractall(DEST)
        print('Verified', package['package'], package['version'], flush=True)
    (DEST / 'dependencies.json').write_bytes(LOCK.read_bytes())


if __name__ == '__main__': main()
