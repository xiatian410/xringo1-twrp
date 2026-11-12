#!/usr/bin/env python3
"""Inventory indexed evidence bindings without treating old PASS reports as current.

This supplements, never replaces, audit_unified_delivery.py. It checks hashes
and artifact identity, not the adequacy of a test, an asserted case count, or
hardware behavior. Text logs and reports without dependency maps are explicitly
unbound. An inventory with drift or unbound entries exits nonzero.
"""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = Path('/root/AAA/twrp')
MAP_FIELDS = {
    'sources', 'shared_sources', 'test_sources', 'tests', 'headers',
    'configuration', 'artwork', 'emulator_files', 'libfdt_sources',
    'source_files', 'supplemental_files', 'shipped_scripts', 'build_inputs',
    'diagnostic_review_sources', 'review_sources', 'input_reports',
}


def digest(path):
    try:
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    except OSError:
        return None


def is_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def inventory(index, root=ROOT, android=ANDROID):
    image = Path(index['image'])
    if not image.is_absolute():
        image = root / image
    current = digest(image)
    rows = []
    for group in ['checks', 'additional_checks']:
        for entry in index[group]:
            evidence = Path(entry['evidence'])
            if not evidence.is_absolute():
                evidence = root / evidence
            row = dict(group=group, name=entry['name'], evidence=entry['evidence'],
                       dependency_count=0, mismatches=[], unbound_reasons=[])
            actual = digest(evidence)
            if actual != entry['evidence_sha256'] or actual is None:
                row['mismatches'].append(dict(kind='indexed-evidence', path=str(evidence),
                                             expected=entry['evidence_sha256'], actual=actual))
            try:
                body = json.loads(evidence.read_text())
            except (OSError, ValueError, UnicodeError):
                body = None
            if not isinstance(body, dict):
                row['unbound_reasons'].append('no structured dependency bindings (text/missing report)')
            else:
                row['recorded_status'] = body.get('status', body.get('result'))
                if 'image_sha256' in body:
                    row['bound_image_sha256'] = body['image_sha256']
                    if body['image_sha256'] != current or current is None:
                        row['mismatches'].append(dict(kind='artifact', expected=current,
                                                     actual=body['image_sha256']))

                def walk(value, trail=()):
                    if not isinstance(value, dict):
                        return
                    for field, mapping in value.items():
                        if field in MAP_FIELDS and isinstance(mapping, dict):
                            if not all(is_digest(v) for v in mapping.values()):
                                row['unbound_reasons'].append('unsupported dependency map: ' + '.'.join(trail + (field,)))
                                continue
                            for name, expected in mapping.items():
                                base = root
                                # This older suite intentionally uses paths relative
                                # to recovery and tests, as does the full auditor.
                                if field == 'sources' and set(mapping) == {'infomanager.cpp', 'infomanager.hpp', 'data.cpp', 'variables.h'}:
                                    base = android / 'bootable/recovery'
                                elif field == 'test_sources' and set(mapping) == {'settings_persistence_test.py', 'settings_persistence_test.cpp'}:
                                    base = root / 'tests'
                                elif entry['name'] == 'settings-persistence-and-timezone':
                                    base = android / 'bootable/recovery' if field == 'sources' else root / 'tests'
                                path = Path(name)
                                if not path.is_absolute():
                                    path = base / path
                                row['dependency_count'] += 1
                                observed = digest(path)
                                if observed is None or observed != expected:
                                    row['mismatches'].append(dict(kind='dependency', field='.'.join(trail + (field,)),
                                                                 path=str(path), expected=expected, actual=observed))
                        elif isinstance(mapping, dict):
                            walk(mapping, trail + (field,))
                walk(body)
                if row['dependency_count'] == 0:
                    row['unbound_reasons'].append('no checked dependency map; artifact hash alone does not bind a test harness')
            row['binding'] = 'drift' if row['mismatches'] else 'unbound' if row['unbound_reasons'] else 'matched'
            rows.append(row)
    counts = {key: sum(r['binding'] == key for r in rows) for key in ['matched', 'drift', 'unbound']}
    image_matches = current is not None and current == index['image_sha256']
    return dict(status='CURRENT_BINDINGS' if image_matches and counts['drift'] == counts['unbound'] == 0 else 'NOT_CURRENT',
                scope=__doc__, image=str(image), image_sha256=current,
                indexed_image_sha256=index['image_sha256'], image_matches=image_matches,
                functional_completion='not assessed', hardware='not assessed', counts=counts, entries=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=ROOT / 'simulation-report.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inventory(json.loads(args.index.read_text()))
    result['index_sha256'] = digest(args.index)
    result['audit_script_sha256'] = digest(Path(__file__))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'], result['counts'], '; physical functionality not assessed')
    raise SystemExit(0 if result['status'] == 'CURRENT_BINDINGS' else 1)


if __name__ == '__main__':
    main()
