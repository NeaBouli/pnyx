"""Derive HTTP calls from production mobile TS/TSX files in a tree or Git ref.

The token scanner retains templates as one argument, strips comments and pairs
parentheses, so methods belong to the enclosing call rather than the next call.
Client helpers are inventoried even if currently unused. No network is needed.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOKENS = re.compile(r'(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<string>`(?:\\.|[^`\\])*`|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(?P<token>[()]|[^()\'"`/]+|/)', re.MULTILINE)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True)


def calls_in_source(source, filename):
    tokens = list(TOKENS.finditer(source))
    stack, calls = [], []
    # Every literal API argument must be inside a call. This intentionally also
    # catches newly introduced wrappers without a hand-maintained helper list.
    for token in tokens:
        if token.lastgroup == 'comment':
            continue
        value = token.group()
        if value == '(':
            stack.append(token.start())
        elif value == ')':
            if stack:
                start = stack.pop()
                calls.append((start, token.end()))
    found = []
    for start, end in calls:
        prefix = source[max(0, start - 100):start]
        name = re.search(r'([\w.]+)(?:<[^<>]*>)?\s*$', prefix)
        if not name or name[1].split('.')[-1] not in {'fetch', 'fetchImpl', 'fetchJsonWithTimeout', 'request'}:
            continue
        if re.search(r'\bfunction\s+' + re.escape(name[1]) + r'(?:<[^<>]*>)?\s*$', prefix):
            continue
        arguments = source[start:end]
        if '/api/v' in arguments:
            continue
        # Reviewed URL-forwarding trampolines. Any new indirection fails closed
        # until resolved here; a call cannot disappear merely by using a variable.
        forwarded = (
            filename == 'apps/mobile/src/lib/api.ts'
            and re.fullmatch(r'\(`\$\{API_(?:MIRROR_)?BASE\}\$\{path\}`, init\)', arguments)
        ) or (
            filename == 'apps/mobile/src/lib/key-rotation.ts'
            and (arguments == '(...args)' or arguments.startswith('(url, { ...init,'))
        )
        assert forwarded, f'Unresolved HTTP call: {filename}:{source.count(chr(10), 0, start) + 1}'
    for token in tokens:
        if token.lastgroup != 'string':
            continue
        literal = token.group()[1:-1]
        if '/api/v' not in literal:
            continue
        parents = [(start, end) for start, end in calls if start < token.start() < end]
        if not parents:
            # Constants and prose aren't HTTP calls. A new API URL constant
            # fails closed until the scanner supports its indirection.
            raise AssertionError(f'Unresolved API literal: {filename}:{source.count(chr(10), 0, token.start()) + 1}')
        start, end = max(parents)
        # Method is in options AFTER the URL (fetchJsonWithTimeout has a deps
        # argument before it). Default fetch/request method is GET.
        options = source[token.end():end]
        method = re.search(r'\bmethod\s*:\s*["\'](GET|POST|PUT|PATCH|DELETE)["\']', options)
        if not method and re.search(r'\bmethod\s*[:,}]', options):
            raise AssertionError(f'Unresolved HTTP method: {filename}')
        method = method[1] if method else 'GET'
        path = literal[literal.index('/api/v'):].split('?')[0]
        # A query-string helper appended to a static path (tickets${params}).
        path = re.sub(r'(?<!/)\$\{params\}$', '', path)
        path = re.sub(r'\$\{[^}]+\}', '{param}', path)
        found.append({'method': method, 'path': path, 'source': f'{filename}:{source.count(chr(10), 0, token.start()) + 1}'})
    return found


def released_calls(ref=None):
    if ref is None:
        paths = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / 'apps/mobile/src').rglob('*')
                       if path.is_file())
    else:
        paths = git('ls-tree', '-r', '--name-only', ref, '--', 'apps/mobile/src').splitlines()
    calls = []
    for path in paths:
        if not path.endswith(('.ts', '.tsx')) or re.search(r'\.(test|spec)\.tsx?$', path) or '/__tests__/' in path:
            continue
        source = (ROOT / path).read_text() if ref is None else git('show', f'{ref}:{path}')
        calls.extend(calls_in_source(source, path))
    return sorted(calls, key=lambda row: (row['path'], row['method'], row['source']))


if __name__ == '__main__':
    import json
    print(json.dumps(released_calls(), indent=2))
