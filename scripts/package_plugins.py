#!/usr/bin/env python3
"""Build one deterministic ZIP per plugin; never include task data or caches."""
import hashlib
import json
from pathlib import Path
import zipfile
from validate_catalog import ROOT, validate


def build():
    validate()
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    checksums = []
    catalog = json.loads((ROOT / '.agents/plugins/marketplace.json').read_text())
    for entry in catalog['plugins']:
        package = ROOT / entry['source']['path']
        manifest = json.loads((package / 'plugin.json').read_text())
        target = output / f'{manifest["name"]}-{manifest["version"]}.zip'
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(package.rglob('*')):
                if not file.is_file() or '__pycache__' in file.parts or file.suffix == '.pyc':
                    continue
                info = zipfile.ZipInfo(str(file.relative_to(package)), (2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, file.read_bytes())
        checksums.append(hashlib.sha256(target.read_bytes()).hexdigest() + '  ' + target.name)
        print(target.relative_to(ROOT))
    (output / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n')


if __name__ == '__main__':
    build()
