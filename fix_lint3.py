"""Rewrite nested-tuple regex blocks into clean parenthesized strings.

Current (broken, from ruff unsafe-fix):
        (
            (
                r"..."
                r"..."
            ),
        ),
  -> list element is a 1-tuple; re.compile() crashes.

Target (string element, ISC004-compliant):
        (
            r"..."
            r"..."
        ),
"""
import io
import os

ROOT = "C:/Users/KIRA/CyberGuide"
path = os.path.join(ROOT, "src/interntrack/services/ai_resume_enhancer.py")

with io.open(path, "r", encoding="utf-8", newline="") as f:
    text = f.read()

# Each replacement: old (nested tuple) -> new (clean paren string)
REPLACEMENTS = [
    (
        '        (\n'
        '            (\n'
        '                r"(?:performed?|conducted?|executed?|carried out?)"\n'
        '                r"\\s+(?:a\\s+)?(?:penetration|pen|vulnerability)"\n'
        '                r"\\s+(?:test|assessment)"\n'
        '            ),\n'
        '        ),\n',
        '        (\n'
        '            r"(?:performed?|conducted?|executed?|carried out?)"\n'
        '            r"\\s+(?:a\\s+)?(?:penetration|pen|vulnerability)"\n'
        '            r"\\s+(?:test|assessment)"\n'
        '        ),\n',
    ),
    (
        '        (\n'
        '            (\n'
        '                r"(?:monitored?|analyzed?|investigated?)"\n'
        '                r"\\s+(?:security|siem|log|alert)"\n'
        '            ),\n'
        '        ),\n',
        '        (\n'
        '            r"(?:monitored?|analyzed?|investigated?)"\n'
        '            r"\\s+(?:security|siem|log|alert)"\n'
        '        ),\n',
    ),
    (
        '        (\n'
        '            (\n'
        '                r"(?:siem|splunk|sentinel|qradar)"\n'
        '                r"\\s+(?:dashboard|query|analysis)"\n'
        '            ),\n'
        '        ),\n',
        '        (\n'
        '            r"(?:siem|splunk|sentinel|qradar)"\n'
        '            r"\\s+(?:dashboard|query|analysis)"\n'
        '        ),\n',
    ),
    (
        '        (\n'
        '            (\n'
        '                r"(?:analyzed?|reverse engineered?|dissected?)"\n'
        '                r"\\s+(?:malware|virus|trojan|ransomware)"\n'
        '            ),\n'
        '        ),\n',
        '        (\n'
        '            r"(?:analyzed?|reverse engineered?|dissected?)"\n'
        '            r"\\s+(?:malware|virus|trojan|ransomware)"\n'
        '        ),\n',
    ),
    (
        '        (\n'
        '            (\n'
        '                r"(?:s3|ec2|lambda|iam|guardduty|security hub)"\n'
        '                r"\\s+(?:configuration|hardening|audit)"\n'
        '            ),\n'
        '        ),\n',
        '        (\n'
        '            r"(?:s3|ec2|lambda|iam|guardduty|security hub)"\n'
        '            r"\\s+(?:configuration|hardening|audit)"\n'
        '        ),\n',
    ),
]

# git block may be indented 16 spaces with triple lines
REPLACEMENTS.append(
    (
        '                (\n'
        '                    (\n'
        '                        r"(?:committed?|pushed?|merged?)"\n'
        '                        r"\\s+(?:code|changes)\\s+(?:to|in)"\n'
        '                        r"\\s+(?:git|github)"\n'
        '                    ),\n'
        '                ),\n',
        '                (\n'
        '                    r"(?:committed?|pushed?|merged?)"\n'
        '                    r"\\s+(?:code|changes)\\s+(?:to|in)"\n'
        '                    r"\\s+(?:git|github)"\n'
        '                ),\n',
    ),
)

# generic fallback: un-nest any "(\n            (\n ... ),\n        )," pattern
import re as _re

nested_re = _re.compile(
    r"(?P<indent> +)\(\n"
    r"(?P<inner> +)\(\n"
    r"(?P<body>(?:.*\n)*?)"
    r"(?P=inner)\)\n"
    r"(?P=indent)\),\n"
)

count = 0
for old, new in REPLACEMENTS:
    if old in text:
        text = text.replace(old, new, 1)
        count += 1

# Apply generic un-nesting for any remaining nested pattern
text2 = nested_re.sub(lambda m: f"{m.group('indent')}(\n{m.group('body')}{m.group('indent')}),\n", text)
if text2 != text:
    count += 1
    text = text2

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(text)

import py_compile

py_compile.compile(path, doraise=True)
print(f"rewrote {count} blocks; compile OK")
