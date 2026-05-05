"""Shared benchmark client/server message contract.

This package owns the on-the-wire message types. The client re-exports them
from ``asimovbm_client.protocol`` for backwards compatibility.

Real content lands in Unit 1; this stub only reserves the import surface so
Unit 0 import gates pass.
"""

from __future__ import annotations

__all__: list[str] = []
