"""Scan installed skills and write a self-contained, searchable HTML report."""
import argparse
import html
import json
import os
import hashlib
import re
from pathlib import Path

from scan_skills import scan


def read_description(directory):
    """Read common frontmatter string forms without executing skill content."""
    path = Path(directory) / 'SKILL.md'
    try:
        text = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError):
        return '描述无法读取'
    frontmatter = re.match(r'\A---\s*\n(.*?)\n---\s*(?:\n|$)', text, re.S)
    if not frontmatter:
        return ''
    lines = frontmatter[1].splitlines()
    for index, line in enumerate(lines):
        match = re.match(r'^description:\s*(.*)$', line)
        if not match:
            continue
        value = match[1].strip()
        continuation = []
        for following in lines[index + 1:]:
            if following.strip() and not following[0].isspace():
                break
            continuation.append(following.strip())
        if re.fullmatch(r'[>|][1-9+-]*', value):
            value = ' '.join(continuation)
        else:
            value = ' '.join([value, *continuation]).strip()
            if value.startswith('"'):
                try:
                    value = json.loads(value)
                except (ValueError, TypeError):
                    value = value[1:-1] if value.endswith('"') else value
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("''", "'")
            else:
                value = re.split(r'\s+#', value, maxsplit=1)[0]
        return ' '.join(value.split())
    return ''


def render(report):
    home = str(Path.home())
    rows = []
    skills = sorted(report['skills'], key=lambda skill: (
        skill['tool'].casefold() == '.agents',
        skill['tool'].casefold(),
        skill['name'].casefold(),
        skill['directory'].casefold(),
    ))
    for skill in skills:
        tool = skill['tool'].casefold()
        hue = {'.agents': 158, '.codex': 265, '.cursor': 210}.get(
            tool, int(hashlib.sha256(tool.encode()).hexdigest()[:8], 16) % 360)
        directory = skill['directory']
        description = read_description(directory)
        description_html = (f'<div class="description" title="{html.escape(description, quote=True)}">'
                            f'{html.escape(description)}</div>' if description else '')
        prefix = home + os.sep
        display = ('~/' + directory[len(prefix):].replace('\\', '/')
                   if os.path.normcase(directory).startswith(os.path.normcase(prefix))
                   else directory)
        target = (f'<div class="target" title="软链接目标"><span class="target-label">软链接</span> ↳ {html.escape(skill["target"])}</div>'
                  if skill['linked'] else '')
        search = ' '.join((skill['name'], description, skill['tool'], directory, display, skill['target']))
        rows.append(f'<tr data-group="{html.escape(tool, quote=True)}" data-search="{html.escape(search, quote=True)}">'
                    f'<td>{html.escape(skill["name"])}{description_html}</td>'
                    f'<td><span class="directory" style="--hue:{hue}">{html.escape(skill["tool"])}</span></td>'
                    f'<td><span title="{html.escape(directory, quote=True)}">'
                    f'{html.escape(display)}</span>{target}</td></tr>')
    warnings = ''
    if report['errors']:
        warnings = '<aside role="alert">部分目录未能读取，清单可能不完整。<ul>' + ''.join(
            f'<li>{html.escape(e["path"])}：{html.escape(e["error"])}</li>'
            for e in report['errors']) + '</ul></aside>'
    template = (Path(__file__).parent.parent / 'assets' / 'inventory.html').read_text(encoding='utf-8')
    # One-pass replacement avoids treating a filename as a template token.
    import re
    values = {'HOME': html.escape(home), 'ROWS': ''.join(rows), 'WARNINGS': warnings,
              'EMPTY': '未找到匹配的技能' if rows else '在已扫描范围内未发现技能',
              'HIDDEN': ' hidden' if rows else ''}
    return re.sub(r'\{\{(HOME|ROWS|WARNINGS|EMPTY|HIDDEN)\}\}',
                  lambda match: values[match[1]], template)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=os.getcwd())
    parser.add_argument('--root', action='append', default=[])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = scan(args.project, args.root)
    output = Path(args.output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(report), encoding='utf-8')
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps({'html': str(output), 'installation_count': report['installation_count'],
                      'physical_directory_count': report['physical_directory_count'],
                      'errors': report['errors']}, ensure_ascii=False, indent=2))
