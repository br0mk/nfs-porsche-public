"""Check the staged publication inventory; no claim of legal clearance is made."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BINARY_MAGIC = (b'MZ', b'\x7fELF', b'\x00asm', b'PK\x03\x04', b'\x89PNG', b'\xff\xd8\xff')
FORBIDDEN = {'work', 'out', 'build', 'dist', 'tools', 'evidence', 'recon', '.venv', 'node_modules'}
EXTENSIONS = {'.py', '.swift', '.html', '.md', '.toml', '.txt', '.yml', '.json'}
SPECIAL = {'.gitignore', 'LICENSE'}


def main():
    inventory = ROOT / 'publication-files.txt'
    allowed = set(inventory.read_text().splitlines())
    result = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--stage', '-z'], capture_output=True)
    if result.returncode:
        print('Run this check inside the standalone Git repository after staging its files.', file=sys.stderr)
        return 1
    errors = []
    seen = set()
    for entry in result.stdout.split(b'\0'):
        if not entry:
            continue
        metadata, pathbytes = entry.split(b'\t', 1)
        mode, oid, stage = metadata.decode().split()
        path = pathbytes.decode()
        seen.add(path)
        if path not in allowed:
            errors.append(f'unreviewed file: {path}')
        if mode not in {'100644', '100755'} or stage != '0':
            errors.append(f'symlink, submodule, or unresolved entry: {path}')
            continue
        parts = Path(path).parts
        if parts[0] in FORBIDDEN or any(x in {'.git', '.build', '__pycache__'} for x in parts):
            errors.append(f'prohibited artifact directory: {path}')
        if path not in SPECIAL and Path(path).suffix not in EXTENSIONS:
            errors.append(f'unapproved file type: {path}')
        data = subprocess.check_output(['git', '-C', str(ROOT), 'cat-file', 'blob', oid])
        if b'\0' in data or data.startswith(BINARY_MAGIC):
            errors.append(f'binary content: {path}')
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            errors.append(f'non-UTF-8 content: {path}')
            continue
        if len(data) > 100_000:
            errors.append(f'large file requires separate review: {path}')
        if path != 'scripts/check_publication.py' and re.search(rb'/Users/|/home/[^/\s]+/', data):
            errors.append(f'personal absolute path: {path}')
        if Path(path).suffix == '.md' and re.search('[А-Яа-яЁё]', text):
            errors.append(f'non-English Markdown: {path}')
    if allowed != seen:
        errors.extend(f'inventory entry not staged: {p}' for p in sorted(allowed - seen))
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Publication inventory passed: {len(seen)} staged text files.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
