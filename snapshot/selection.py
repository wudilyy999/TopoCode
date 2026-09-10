import os
from collections import defaultdict, deque


MANIFESTS = frozenset({
    'package.json', 'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt',
    'go.mod', 'cargo.toml', 'pom.xml', 'build.gradle', 'build.gradle.kts',
    'dockerfile', 'compose.yaml', 'compose.yml', 'docker-compose.yml',
    'makefile', 'cmakelists.txt', 'tsconfig.json', 'vite.config.ts',
    'webpack.config.js', 'next.config.js', 'next.config.mjs', 'readme.md',
})
ENTRY_STEMS = frozenset({'main', '__main__', 'app', 'application', 'server', 'index',
                         'bootstrap', 'cli', 'manage', 'wsgi', 'asgi', 'program'})
ROLE_PARTS = frozenset({'routes', 'router', 'routing', 'registry', 'plugins', 'middleware',
                        'auth', 'config', 'settings', 'migrations', 'schema', 'models',
                        'controllers', 'services', 'api'})
SOURCE_SUFFIXES = frozenset({'.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.go',
                            '.rs', '.java', '.kt', '.cs', '.cpp', '.c', '.h', '.rb', '.php',
                            '.vue', '.svelte', '.html', '.sql', '.yaml', '.yml', '.toml'})


def file_role(path):
    parts = path.lower().split('/')
    name = parts[-1]
    stem, suffix = os.path.splitext(name)
    if name in MANIFESTS:
        return 'manifest'
    if suffix in SOURCE_SUFFIXES and (stem in ENTRY_STEMS or stem.endswith('application')):
        return 'entry'
    if suffix in SOURCE_SUFFIXES and (set(parts[:-1]) | set(stem.replace('-', '_').split('_'))) & ROLE_PARTS:
        return 'registration/configuration'
    return ''


def select_files(paths, limit, scores=None):
    scores = scores or {}
    ordered = sorted(set(paths), key=lambda p: (-scores.get(p, 0), p))
    roles = {p: file_role(p) for p in ordered}
    critical = [p for p in ordered if roles[p]]
    groups = defaultdict(deque)
    for path in ordered:
        groups[os.path.dirname(path) or '(root)'].append(path)
    chosen, reasons = [], {}

    def add(path, reason):
        if path not in reasons and len(chosen) < limit:
            chosen.append(path)
            reasons[path] = reason

    bounded = len(ordered) > limit
    critical_budget = max(1, limit * 3 // 5) if bounded else limit
    role_queues = {}
    for role in ('manifest', 'entry', 'registration/configuration'):
        buckets = defaultdict(deque)
        for path in critical:
            if roles[path] == role:
                buckets[os.path.dirname(path) or '(root)'].append(path)
        role_queues[role] = deque(sorted(buckets.values(), key=lambda q: (
            q[0].count('/'), -scores.get(q[0], 0), q[0])))
    while any(role_queues.values()) and len(chosen) < min(limit, critical_budget):
        for role, queue in role_queues.items():
            if queue and len(chosen) < min(limit, critical_budget):
                bucket = queue.popleft()
                add(bucket.popleft(), role)
                if bucket:
                    queue.append(bucket)
    covered = {os.path.dirname(p) or '(root)' for p in chosen}
    directory_limit = min(limit, len(chosen) + limit // 5) if bounded else limit
    representatives = []
    for directory, candidates in groups.items():
        if directory not in covered:
            representatives.append(next((p for p in candidates if os.path.splitext(p)[1].lower() in SOURCE_SUFFIXES), candidates[0]))
    for path in sorted(representatives, key=lambda p: (p.count('/'), -scores.get(p, 0), p)):
        if len(chosen) >= directory_limit:
            break
        add(path, 'directory coverage')
    for path in ordered:
        add(path, 'dependency rank')
    missing = [p for p in critical if p not in reasons]
    covered = {os.path.dirname(p) or '(root)' for p in chosen}
    return chosen, {
        'total': len(ordered), 'selected': len(chosen), 'omitted': len(ordered)-len(chosen),
        'critical_total': len(critical), 'critical_omitted': len(missing),
        'critical_omitted_examples': missing[:20],
        'directories_total': len(groups), 'directories_covered': len(covered),
        'stage_counts': {
            'critical': sum(reason in role_queues for reason in reasons.values()),
            'directory': sum(reason == 'directory coverage' for reason in reasons.values()),
            'dependency': sum(reason == 'dependency rank' for reason in reasons.values()),
        },
        'reasons': reasons,
    }
