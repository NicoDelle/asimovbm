from __future__ import annotations

import re

from asimovbm_client.protocol import FailureMessage


TOKEN_RE = re.compile(r"(?i)(token|secret|password|key)=([^\s]+)")
ABSOLUTE_PATH_RE = re.compile(r"(?<!\w)/(?:[\w.-]+/)+[\w.-]+")


def redact_text(value: str) -> str:
    redacted = TOKEN_RE.sub(r"\1=<redacted>", value)
    redacted = ABSOLUTE_PATH_RE.sub("<path>", redacted)
    return redacted


def summarize_failures(failures: list[FailureMessage]) -> list[str]:
    return [
        f"{failure.category.value}: {redact_text(failure.summary)}"
        for failure in failures
    ]
