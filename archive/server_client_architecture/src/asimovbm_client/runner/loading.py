from __future__ import annotations

import importlib
from typing import Any


class ParticipantCodeError(RuntimeError):
    """Raised when local participant code cannot be loaded or called."""


def load_callable(reference: str) -> Any:
    module_name, separator, attribute_name = reference.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ParticipantCodeError(
            "Participant references must use 'module:attribute' format"
        )

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ParticipantCodeError(f"Could not import participant module {module_name!r}") from exc

    try:
        target = getattr(module, attribute_name)
    except AttributeError as exc:
        raise ParticipantCodeError(
            f"Participant module {module_name!r} has no attribute {attribute_name!r}"
        ) from exc

    try:
        instance = target() if isinstance(target, type) else target
    except Exception as exc:
        raise ParticipantCodeError(
            f"Could not construct participant object {reference!r}"
        ) from exc

    if not callable(instance):
        raise ParticipantCodeError(f"Participant object {reference!r} is not callable")
    return instance
