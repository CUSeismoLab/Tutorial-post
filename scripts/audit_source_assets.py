#!/usr/bin/env python3
"""Copy unchanged course assets and audit RST references before migration.

Usage: python3 scripts/audit_source_assets.py /path/to/cuseistut/docs/source --copy
The source tree is read-only. Existing matching destination files are retained.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit


def included(path, root):
    rel = path.relative_to(root)
    return (
        path.is_file()
        and not any(part.startswith('.') or part == '__pycache__' for part in rel.parts)
        and path.suffix.lower() not in {'.rst', '.pyc'}
        and rel.as_posix() != 'conf.py'
    )


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def exact_case_exists(path):
    """Check spelling as well as existence, including on case-insensitive macOS."""
    if not path.exists():
        return False
    return all(part.name in {p.name for p in part.parent.iterdir()} for part in [path, *path.parents] if part != part.parent)


def references(text):
    patterns = [
        ('image', r'^[ \t]*\.\.[ \t]+(?:image|figure)[ \t]*::[ \t]*(.+)$'),
        ('download', r':download:`([^`]+)`'),
        ('link', r'`[^`\n]*<([^>]+)>`_{1,2}'),
        ('target', r'^[ \t]*\.\.[ \t]+_[^:\n]+:[ \t]+(.+)$'),
    ]
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text, re.M | re.I):
            value = match.group(1).strip()
            if kind == 'download':
                value = value.split('<')[-1].rstrip('>').strip()
            yield kind, value, text.count('\n', 0, match.start()) + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--destination', type=Path, default=Path(__file__).resolve().parents[1] / 'public' / 'media')
    parser.add_argument('--copy', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    assets = sorted(path for path in source.rglob('*') if included(path, source))
    mismatches = []
    for path in assets:
        target = destination / path.relative_to(source)
        if args.copy:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or digest(path) != digest(target):
                shutil.copy2(path, target)
        if not target.is_file() or digest(path) != digest(target):
            mismatches.append(str(path.relative_to(source)))

    missing, case_mismatches, remote_images = [], [], []
    counts = {}
    local_references = 0
    for path in sorted(source.rglob('*.rst')):
        for kind, value, line in references(path.read_text()):
            counts[kind] = counts.get(kind, 0) + 1
            parsed = urlsplit(value)
            entry = {'source': str(path.relative_to(source)), 'line': line, 'kind': kind, 'target': value}
            if parsed.scheme or parsed.netloc:
                if kind == 'image':
                    remote_images.append(entry)
                continue
            if not parsed.path:
                continue
            local_references += 1
            target = (path.parent / unquote(parsed.path)).resolve()
            if not target.exists():
                missing.append(entry)
            elif not exact_case_exists(target):
                case_mismatches.append(entry)

    print(json.dumps({
        'asset_count': len(assets),
        'total_bytes': sum(path.stat().st_size for path in assets),
        'largest_file': str(max(assets, key=lambda p: p.stat().st_size).relative_to(source)),
        'largest_bytes': max(path.stat().st_size for path in assets),
        'reference_counts': counts,
        'local_reference_count': local_references,
        'missing_source_references': missing,
        'case_mismatches': case_mismatches,
        'destination_byte_mismatches': mismatches,
        'remote_images': remote_images,
    }, indent=2))
    return 1 if missing or case_mismatches or mismatches else 0


if __name__ == '__main__':
    raise SystemExit(main())
