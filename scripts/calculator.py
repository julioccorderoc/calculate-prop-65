"""Backwards-compatible re-export of ``calculate_lead_exposure``.

The function itself lives in :mod:`scripts.models` now — validation moved
onto the dataclass ``__post_init__`` methods, so the old wrapper's only
remaining job was picking a public name. This shim exists solely because
``scripts/calculate.py`` (the CLI entry point) imports via
``from .calculator import calculate_lead_exposure`` and that import path is
also used by external consumers that predate the refactor.

New code should import from :mod:`scripts` directly.
"""

from __future__ import annotations

from .models import calculate_lead_exposure

__all__ = ["calculate_lead_exposure"]
