#!/usr/bin/env python3
"""Check maintained documentation entry points without requiring local blobs/logs.

Historical technical reports deliberately reference private evidence. This check
does not claim that every historical local evidence link exists in the export.
"""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENTRY_POINTS = (
    'README.md', 'CONTRIBUTING.md', 'ADAPTATION-GOALS.md', 'BUILD-AND-TEST.md',
    'MAINTENANCE.md', 'FEATURE-USAGE.md', 'compatibility-matrix.md',
    'simulation-report.md', 'FIRMWARE-MAP.md', 'docs/README.md', 'docs/WORK-QUEUE.md',
    'dtsrc/O1_asic_dual/README.md',
    'docs/STATUS-ADAPTATION.md', 'docs/SETTINGS-ADAPTATION.md',
    'docs/FILESYSTEM-TOOLS-EXECUTION.md', 'docs/INSTALL-CHAIN-VALIDATION.md',
    'docs/OTA-OPERATION-COW.md',
)


TECHNICAL_REPORTS = frozenset(ENTRY_POINTS[-5:])

def main():
    links = 0
    for name in ENTRY_POINTS:
        path = ROOT / name
        text = path.read_text()
        assert text.startswith('# '), f'{name}: missing document title'
        assert len(re.findall(r'^# ', text, re.M)) == 1, f'{name}: multiple H1 titles'
        assert text.endswith('\n'), f'{name}: missing final newline'
        assert not any(line.rstrip() != line for line in text.splitlines()), name
        # Ignore code examples; only maintained navigation links are in scope.
        prose = re.sub(r'^```.*?^```[^\n]*$', '', text, flags=re.M | re.S)
        for raw in re.findall(r'\]\(([^)\n]+)\)', prose):
            target = raw.strip().strip('<>')
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            assert not url.path.startswith('/'), f'{name}: local absolute link {target}'
            resolved = (path.parent / unquote(url.path)).resolve()
            assert resolved.is_relative_to(ROOT.resolve()), f'{name}: link escapes repository'
            # Historical technical evidence is kept private, as documented.
            relative = resolved.relative_to(ROOT.resolve())
            if name in TECHNICAL_REPORTS and relative.parts[0] in {'logs', 'imgs', 'backups', 'firmware'}:
                continue
            assert resolved.exists(), f'{name}: missing link {target}'
            links += 1
    readme = (ROOT / 'README.md').read_text()
    badge = re.search(r'actions/workflows/([^/]+\.yml)/badge\.svg', readme)
    assert badge and (ROOT / '.github/workflows' / badge[1]).is_file(), 'README workflow badge'
    print(f'PASS: {len(ENTRY_POINTS)} maintained documentation entries, {links} local links and workflow badge')


if __name__ == '__main__':
    main()
