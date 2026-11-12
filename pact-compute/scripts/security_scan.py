"""Scan reviewed source paths for common live-secret formats without displaying values."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / 'reports' / 'final-validation'
PATTERNS = {
    'aws-access-key': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    'groq-key': re.compile(r'\bgsk_[A-Za-z0-9]{25,}\b'),
    'openai-key': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b'),
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=REPORTS)
    args = parser.parse_args()
    tracked = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    findings = []
    count = 0
    for name in tracked:
        path = ROOT / name
        if path.suffix not in {'.py', '.ts', '.tsx', '.js', '.json', '.md', '.yml', '.yaml', '.txt', '.log', '.xml', '.example', '.sh', '.ps1'}:
            continue
        if not path.is_file():
            continue
        count += 1
        for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            for kind, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append({'path': name, 'line': number, 'kind': kind})
    forbidden = [name for name in tracked if Path(name).name in {'.env', 'deploy.env', 'local-credentials.json', 'market-credentials.json', 'env'}]
    result = {'reviewable_text_files_scanned': count, 'findings': findings, 'forbidden_reviewable_files': forbidden,
              'scope': 'Current tracked and reviewable untracked text files, common key formats only; no private env/state reads and no proof about all history or arbitrary secrets'}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'secret-scan.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'Scanned {count} tracked text files; {len(findings)} format findings; {len(forbidden)} forbidden tracked files')
    return int(bool(findings or forbidden))


if __name__ == '__main__':
    raise SystemExit(main())
