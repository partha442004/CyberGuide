"""Fix remaining ISC004 + E501 issues in ai_resume_enhancer.py and jwt.py."""
import io
import os

ROOT = "C:/Users/KIRA/CyberGuide"


def patch(path, replacements):
    full = os.path.join(ROOT, path)
    with io.open(full, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    for old, new in replacements:
        if old not in text:
            print(f"WARN not found in {path}: {old[:60]!r}")
            continue
        text = text.replace(old, new, 1)
    with io.open(full, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"patched {path}")


# ai_resume_enhancer.py
patch(
    "src/interntrack/services/ai_resume_enhancer.py",
    [
        # penetration_testing: wrap in parens (ISC004)
        (
            '        r"(?:performed?|conducted?|executed?|carried out?)"\n'
            '        r"\\s+(?:a\\s+)?(?:penetration|pen|vulnerability)"\n'
            '        r"\\s+(?:test|assessment)",\n',
            '        (\n'
            '            r"(?:performed?|conducted?|executed?|carried out?)"\n'
            '            r"\\s+(?:a\\s+)?(?:penetration|pen|vulnerability)"\n'
            '            r"\\s+(?:test|assessment)",\n'
            '        ),\n',
        ),
        # soc_analyst first: wrap in parens (ISC004)
        (
            '        r"(?:monitored?|analyzed?|investigated?)"\n'
            '        r"\\s+(?:security|siem|log|alert)",\n',
            '        (\n'
            '            r"(?:monitored?|analyzed?|investigated?)"\n'
            '            r"\\s+(?:security|siem|log|alert)",\n'
            '        ),\n',
        ),
        # soc_analyst third: wrap in parens (ISC004)
        (
            '        r"(?:siem|splunk|sentinel|qradar)"\n'
            '        r"\\s+(?:dashboard|query|analysis)",\n',
            '        (\n'
            '            r"(?:siem|splunk|sentinel|qradar)"\n'
            '            r"\\s+(?:dashboard|query|analysis)",\n'
            '        ),\n',
        ),
        # malware_analysis first line too long (94)
        (
            '        r"(?:analyzed?|reverse engineered?|dissected?)\\s+(?:malware|virus|trojan|ransomware)",\n',
            '        (\n'
            '            r"(?:analyzed?|reverse engineered?|dissected?)"\n'
            '            r"\\s+(?:malware|virus|trojan|ransomware)",\n'
            '        ),\n',
        ),
        # cloud_security second line too long (92)
        (
            '        r"(?:s3|ec2|lambda|iam|guardduty|security hub)\\s+(?:configuration|hardening|audit)",\n',
            '        (\n'
            '            r"(?:s3|ec2|lambda|iam|guardduty|security hub)"\n'
            '            r"\\s+(?:configuration|hardening|audit)",\n'
            '        ),\n',
        ),
        # git first: wrap in parens (ISC004) + too long (90)
        (
            '                r"(?:committed?|pushed?|merged?)"\n'
            '                r"\\s+(?:code|changes)\\s+(?:to|in)"\n'
            '                r"\\s+(?:git|github)",\n',
            '                (\n'
            '                    r"(?:committed?|pushed?|merged?)"\n'
            '                    r"\\s+(?:code|changes)\\s+(?:to|in)"\n'
            '                    r"\\s+(?:git|github)",\n'
            '                ),\n',
        ),
        # git version-control line too long (90)
        (
            '                r"(?:version control|git|github|gitlab)\\s+(?:experience|knowledge|usage)",\n',
            '                (\n'
            '                    r"(?:version control|git|github|gitlab)"\n'
            '                    r"\\s+(?:experience|knowledge|usage)",\n'
            '                ),\n',
        ),
        # role_patterns: wrap in parens (ISC004)
        (
            "            (\n"
            '                r"(?:seeking|looking for|interested in|pursuing)"\n'
            '                r"\\s+(?:a\\s+)?(.*?)"\n'
            '                r"(?:\\s+position|\\s+role|\\s+job|\\s+career|\\.|,|$)",\n',
            "            (\n"
            "                (\n"
            '                    r"(?:seeking|looking for|interested in|pursuing)"\n'
            '                    r"\\s+(?:a\\s+)?(.*?)"\n'
            '                    r"(?:\\s+position|\\s+role|\\s+job|\\s+career|\\.|,|$)",\n'
            "                ),\n",
        ),
    ],
)

# jwt.py E501 line 164
patch(
    "src/interntrack/auth/jwt.py",
    [
        (
            '        raise HTTPException(status_code=401, detail="Invalid or expired token") from None\n',
            "        raise HTTPException(\n"
            '            status_code=401, detail="Invalid or expired token"\n'
            "        ) from None\n",
        ),
    ],
)

print("done")
