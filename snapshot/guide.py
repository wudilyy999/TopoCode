import ast
import os

from snapshot.redact import redact


def build_reading_guide(project, path, details):
    sections = []
    startup = []
    if path.endswith('.py'):
        with open(os.path.join(project, path), encoding='utf-8', errors='replace') as handle:
            content = handle.read(512 * 1024)
        try:
            tree = ast.parse(content)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in tree.body:
                if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
                    operands = [node.test.left, *node.test.comparators]
                    if (any(isinstance(n, ast.Name) and n.id == '__name__' for n in operands)
                            and any(isinstance(n, ast.Constant) and n.value == '__main__' for n in operands)
                            and len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)):
                        calls = [ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)]
                        startup.append({'name': '__main__', 'line': node.lineno, 'end_line': node.end_lineno,
                                        'calls': calls, 'kind': 'startup'})
                members = [(node, '')]
                if isinstance(node, ast.ClassDef):
                    members += [(member, node.name + '.') for member in node.body
                                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))]
                for item, prefix in members:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        continue
                    name = prefix + item.name
                    calls = list(dict.fromkeys(ast.unparse(n.func) for n in ast.walk(item)
                                               if isinstance(n, ast.Call)))[:12]
                    doc = (ast.get_docstring(item) or '').split('\n')[0]
                    sections.append({'name': name, 'line': item.lineno, 'end_line': item.end_lineno,
                                     'kind': 'class' if isinstance(item, ast.ClassDef) else 'function',
                                     'purpose': redact(doc)[:240], 'calls': calls, 'source': 'syntax'})
    if not sections:
        sections = [{'name': d['name'], 'line': d['line'], 'end_line': d.get('end_line'),
                     'kind': d.get('kind', 'symbol'), 'purpose': redact(d.get('doc', ''))[:240],
                     'calls': [], 'source': 'candidate'} for d in details]
    return {'startup': startup, 'sections': sections, 'source': 'syntax' if path.endswith('.py') else 'candidate'}
