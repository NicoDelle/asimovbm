from __future__ import annotations

import re

from asimovbm_client.protocol import FailureMessage


SECRET_KEY = r"(?:token|secret|password|api[_-]?key|access[_-]?key|key)"
KEY_VALUE_SECRET_RE = re.compile(
    rf"(?i)\b({SECRET_KEY})(\s*[=:]\s*)([^\s,;]+)"
)
QUOTED_SECRET_RE = re.compile(
    rf"(?i)([\"'](?:{SECRET_KEY})[\"']\s*:\s*[\"'])([^\"']+)([\"'])"
)
AUTHORIZATION_RE = re.compile(r"(?i)\b(authorization\s*:\s*)(bearer\s+)?([^\s,;]+)")
ABSOLUTE_PATH_RE = re.compile(r"(?<!\w)/(?:[\w.-]+/)+[\w.-]+")


def redact_text(value: str) -> str:
    redacted = QUOTED_SECRET_RE.sub(r"\1<redacted>\3", value)
    redacted = KEY_VALUE_SECRET_RE.sub(r"\1\2<redacted>", redacted)
    redacted = AUTHORIZATION_RE.sub(r"\1\2<redacted>", redacted)
    redacted = ABSOLUTE_PATH_RE.sub("<path>", redacted)
    return redacted


def summarize_failures(failures: list[FailureMessage]) -> list[str]:
    return [
        f"{failure.category.value}: {redact_text(failure.summary)}"
        for failure in failures
    ]
