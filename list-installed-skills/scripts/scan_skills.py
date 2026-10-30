"""Read-only skill discovery. Standard library only; emits UTF-8 JSON."""
import argparse
import json
import os
from pathlib import Path


EXCLUDED = {
    '.system', '.git', 'node_modules', '__pycache__', '.skills-manager-trash',
    'trash', '.trash', 'cache', '.cache', 'plugins', '.plugins',
}
KNOWN = (
    '.agents/skills', '.cursor/skills', '.codex/skills', '.claude/skills',
    '.github/skills', '.gemini/skills', '.gemini/antigravity/skills',
    '.config/opencode/skills', '.codeium/windsurf/skills', '.roo/skills',
    '.kilocode/skills', '.opencode/skills',
)


def scan(project=None, extra=()):
    roots, rows, errors, skipped = {}, [], [], []

    def error(path, exc):
        errors.append({'path': str(path), 'error': str(exc)})

    def add(path, scope, tool):
        path = Path(os.path.abspath(path))
        roots.setdefault(os.path.normcase(str(path)), (path, scope, tool))

    home = Path.home()
    bases = [(home, '用户级')]
    if project:
        current = Path(project).absolute()
        bases += [(p, '项目级' if p == current else '祖先目录')
                  for p in (current, *current.parents) if p != home]
    for base, scope in bases:
        for relative in KNOWN:
            add(base / relative, scope, relative.rsplit('/skills', 1)[0])
        try:
            for child in base.iterdir():
                if child.name.startswith('.') and child.name.lower() not in EXCLUDED:
                    if child.is_dir():
                        add(child / 'skills', scope, child.name)
        except OSError as exc:
            error(base, exc)
    if os.environ.get('CODEX_HOME'):
        add(Path(os.environ['CODEX_HOME']) / 'skills', '用户级', 'CODEX_HOME')
    if os.environ.get('XDG_CONFIG_HOME'):
        add(Path(os.environ['XDG_CONFIG_HOME']) / 'opencode/skills', '用户级', 'opencode')
    for path in extra:
        add(path, '指定目录', '自定义')

    def walk(path, scope, tool, ancestors):
        try:
            target = path.resolve(strict=True)
            if any(part.lower() in EXCLUDED for part in (*path.parts, *target.parts)):
                skipped.append(str(path))
                return
            key = os.path.normcase(str(target))
            if key in ancestors:
                skipped.append(str(path))
                return
            if (path / 'SKILL.md').is_file():
                rows.append({'name': path.name, 'tool': tool, 'scope': scope,
                             'directory': str(path), 'target': str(target),
                             'linked': os.path.normcase(str(path)) != key})
                return
            for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
                if child.name.lower() in EXCLUDED:
                    skipped.append(str(child))
                elif child.is_dir():
                    walk(child, scope, tool, ancestors | {key})
        except (OSError, RuntimeError) as exc:
            error(path, exc)

    checked = []
    for path, scope, tool in roots.values():
        try:
            path.stat()
        except FileNotFoundError:
            if path.is_symlink():
                error(path, 'Broken symbolic link')
            checked.append({'path': str(path), 'status': 'missing'})
            continue
        except OSError as exc:
            error(path, exc)
            checked.append({'path': str(path), 'status': 'error'})
            continue
        checked.append({'path': str(path), 'status': 'scanned'})
        walk(path, scope, tool, set())
    unique = {os.path.normcase(r['directory']): r for r in rows}
    rows = sorted(unique.values(), key=lambda r: (r['name'].lower(), r['directory']))
    return {'skills': rows, 'installation_count': len(rows),
            'physical_directory_count': len({os.path.normcase(r['target']) for r in rows}),
            'roots': checked, 'skipped': skipped, 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=os.getcwd())
    parser.add_argument('--root', action='append', default=[])
    args = parser.parse_args()
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(scan(args.project, args.root), ensure_ascii=False, indent=2))
