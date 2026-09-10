from snapshot.languages import language_for
from snapshot.selection import file_role


def build_navigation(struct, components):
    ownership = {}
    for component in components.get('components', []):
        for path in component.get('files', []):
            ownership[path] = component
    files = []
    for path in struct['files']:
        component = ownership.get(path, {})
        role = (component.get('file_roles') or {}).get(path, '')
        symbols = struct.get('symbols', {}).get(path, [])
        entry = 'analysis' if path in component.get('entry_files', []) else (
            'candidate' if file_role(path) == 'entry' else '')
        files.append({
            'path': path, 'language': language_for(path),
            'component': component.get('name', ''),
            'component_id': component.get('id', ''),
            'role': role or struct.get('docs', {}).get(path, ''),
            'role_source': 'analysis' if role else 'evidence', 'entry': entry,
            'symbols': [{'name': s['name'], 'line': s['line']} for s in symbols[:8]],
        })
    return {'files': files, 'imports': struct['import_edges'],
            'coverage': struct.get('snapshot_selection', {})}
