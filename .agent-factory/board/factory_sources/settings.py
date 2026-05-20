"""Settings file data access for the Board backend."""

from __future__ import annotations

import os
import re


def _resolve_settings_file(project_root: str) -> str:
    """Return .settings path."""
    return os.path.join(project_root, '.agent-factory', '.settings')


def _parse_env_file(project_root: str) -> list[dict]:
    """Parse .settings into structured sections for the settings UI."""
    env_file = _resolve_settings_file(project_root)
    if not os.path.exists(env_file):
        return []

    sections: dict[str, list[dict]] = {}
    section_order: list[str] = []
    current_section = '기타'
    pending_comment = ''

    with open(env_file, encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()

            # Section header: "# (N) Section Name"
            if stripped.startswith('# (') and ')' in stripped:
                current_section = stripped.split(')', 1)[1].strip()
                if current_section not in sections:
                    sections[current_section] = []
                    section_order.append(current_section)
                pending_comment = ''
                continue

            if stripped.startswith('# ---'):
                continue

            if stripped.startswith('#'):
                text = stripped[1:].strip()
                if text.startswith('용도:'):
                    pending_comment = text[3:].strip()
                continue

            if not stripped or '=' not in stripped:
                continue

            key, _, rest = stripped.partition('=')
            key = key.strip()

            # Extract inline comment (2+ spaces before #)
            value = rest
            inline_comment = ''
            m = re.match(r'^(.*?)\s{2,}#\s*(.*)', rest)
            if m:
                value = m.group(1).strip()
                inline_comment = m.group(2).strip()
            else:
                value = rest.strip()

            # Detect type
            var_type = 'string'
            if value.lower() in ('true', 'false'):
                var_type = 'bool'
            elif value.isdigit():
                var_type = 'int'
            else:
                try:
                    float(value)
                    if '.' in value:
                        var_type = 'float'
                except ValueError:
                    pass

            label = inline_comment or pending_comment or ''
            if current_section not in sections:
                sections[current_section] = []
                section_order.append(current_section)

            sections[current_section].append({
                'key': key,
                'value': value,
                'type': var_type,
                'label': label,
            })
            pending_comment = ''

    return [{'section': s, 'vars': sections[s]} for s in section_order]


def _update_env_value(project_root: str, key: str, new_value: str) -> bool:
    """Update a single key's value in .settings, preserving structure and comments."""
    env_file = _resolve_settings_file(project_root)
    if not os.path.exists(env_file):
        return False

    with open(env_file, encoding='utf-8') as f:
        lines = f.readlines()

    pattern = re.compile(r'^' + re.escape(key) + r'=')

    for i, line in enumerate(lines):
        if not pattern.match(line.strip()):
            continue

        old_rest = line.strip().split('=', 1)[1]
        inline_part = ''
        m = re.match(r'^(.*?)\s{2,}(#\s*.*)', old_rest)
        if m:
            inline_part = m.group(2)

        if inline_part:
            base = f"{key}={new_value}"
            pad = max(2, 40 - len(base))
            lines[i] = base + ' ' * pad + inline_part + '\n'
        else:
            lines[i] = f"{key}={new_value}\n"
        break
    else:
        return False

    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    return True
