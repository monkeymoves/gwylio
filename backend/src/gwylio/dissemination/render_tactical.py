"""The tactical alert: a designed seam, not built in version 1.

A tactical alert would go out the moment a single report crossed a threshold
(a passed horizon on a high impact report, say). Version 1 publishes the
strategic assessment and the monthly INTSUM only; asking for an alert raises
``NotImplementedInV1`` and the command line exits 4.
"""

from __future__ import annotations

from typing import NoReturn

from gwylio.dissemination.model import TACTICAL_MESSAGE, NotImplementedInV1

__all__ = ["render_tactical"]


def render_tactical(*_: object, **__: object) -> NoReturn:
    """Always raises ``NotImplementedInV1``: tactical alerts are not built in version 1."""
    raise NotImplementedInV1(TACTICAL_MESSAGE, scope="product")
