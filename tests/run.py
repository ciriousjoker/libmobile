#!/usr/bin/env python3
"""Run the same named game-protocol contracts against firmware and libmobile."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from zoneinfo import ZoneInfo

from firmware_emulator import Firmware, PROFILES, load_images
from libmobile import Libmobile, SOURCES, build
from report import write_reports
from test_protocol import GameProtocolTests


class Results(unittest.TestResult):
    def __init__(self, target):
        super().__init__()
        self.target = target
        self.records = []

    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()

    def record(self, test, status, detail=''):
        adapter = getattr(test, 'adapter', None)
        substitutions = sorted(set(getattr(getattr(adapter, 'cpu', None), 'substitutions', [])))
        record = {'target': self.target, 'name': test._testMethodName.removeprefix('test_'),
                  'description': test.shortDescription() or '', 'status': status,
                  'detail': detail, 'seconds': round(time.monotonic() - self.started, 4),
                  'exchanges': getattr(adapter, 'history', []), 'substitutions': substitutions}
        self.records.append(record)
        print(f'{status:5} {self.target:20} {record["name"]}')

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, 'PASS')

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.record(test, 'FAIL', str(error[1]))

    def addError(self, test, error):
        super().addError(test, error)
        self.record(test, 'ERROR', self._exc_info_to_string(error, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, 'SKIP', reason)


def main():
    here = Path(__file__).resolve().parent
    root = here.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=('all', 'firmware', 'libmobile'), default='all')
    parser.add_argument('--roms', type=Path, default=here / 'firmware_emulator' / 'roms')
    parser.add_argument('--output', type=Path, default=here / 'reports')
    args = parser.parse_args()
    try:
        # Validate every input before running any tests. Library-only runs need no ROMs.
        images = load_images(args.roms) if args.target != 'libmobile' else [(p, None) for p in PROFILES]
        source_files = sorted(root.glob('*.c')) + sorted(root.glob('*.h'))
        source_hash = hashlib.sha256(b''.join(p.name.encode() + b'\0' + p.read_bytes() for p in source_files)).hexdigest()
        revision = subprocess.run(['git', '-C', str(root), 'log', '-1', '--format=%H', '--',
                                   *(name + '.c' for name in SOURCES)],
                                  check=True, capture_output=True, text=True).stdout.strip()
        records = []
        with tempfile.TemporaryDirectory(prefix='libmobile-tests-') as temporary:
            library = build(root, Path(temporary)) if args.target != 'firmware' else None
            for profile, rom in images:
                targets = []
                if args.target != 'libmobile':
                    targets.append((profile.name + ' firmware', lambda p=profile, r=rom: Firmware(p, r)))
                if args.target != 'firmware':
                    targets.append((profile.name + ' libmobile', lambda p=profile: Libmobile(p, library)))
                for target, factory in targets:
                    case = type('ProtocolTests', (GameProtocolTests, unittest.TestCase), {'factory': staticmethod(factory)})
                    result = Results(target)
                    unittest.defaultTestLoader.loadTestsFromTestCase(case).run(result)
                    records.extend(result.records)
        metadata = {'generated': datetime.now(ZoneInfo('Europe/Berlin')).isoformat(timespec='seconds'),
                    'library_revision': revision, 'library_source_sha256': source_hash,
                    'profiles': [{'name': p.name, 'filename': p.filename, 'sha256': p.sha256} for p in PROFILES]}
        write_reports(args.output, records, metadata)
        totals = Counter(r['status'] for r in records)
        print('\n' + ', '.join(f'{totals[status]} {status}' for status in ('PASS', 'FAIL', 'ERROR', 'SKIP')))
        print(f'Reports: {args.output.resolve()}')
        return int(bool(totals['FAIL'] or totals['ERROR']))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Cannot run suite: {error}', file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
