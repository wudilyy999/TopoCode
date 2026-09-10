import os

from snapshot.redact import redact


def read_code_block(project, path, start, end):
    root = os.path.realpath(project)
    target = os.path.realpath(os.path.join(root, path))
    if os.path.isabs(path) or os.path.commonpath([root, target]) != root:
        raise ValueError('File must be inside the registered project')
    parts = os.path.relpath(target, root).split(os.sep)
    if any(p in ('.git', '.ssh') or p.startswith('.env') for p in parts) or any(
        word in os.path.basename(path).lower() for word in ('credential', 'recovery-codes', 'id_rsa', 'id_ed25519')
    ):
        raise ValueError('Sensitive file access is disabled')
    if start < 1 or end < start or end - start >= 2000:
        raise ValueError('Select a code block of 1–2000 lines')
    with open(target, 'rb') as handle:
        raw = handle.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024 or b'\x00' in raw:
        raise ValueError('Code preview supports text files up to 512 KB')
    text = raw.decode('utf-8')
    lines = text.splitlines()
    if end > len(lines):
        raise ValueError('File changed; reopen the file guide')
    sanitized = [redact(line) for line in lines]
    return {'path': path, 'start_line': start, 'end_line': end,
            'code': '\n'.join(sanitized[start - 1:end])}
