"""Domain errors shared by every context.

Each error carries an optional ``location``: a path inside the configuration
or aggregate that produced it, written the way a JSON path reads, for example
``hazards[2].family``. The ``scope`` names the catalogue or aggregate the
location belongs to (``hazards``, ``requirement_set``), so an outer layer can
map it back to a file without the domain knowing about files.
"""

from __future__ import annotations

__all__ = ["DomainError", "DuplicateId", "UnknownReference"]


class DomainError(Exception):
    """A rule of the domain was broken."""

    def __init__(self, message: str, *, scope: str = "", location: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.scope = scope
        self.location = location

    def __str__(self) -> str:
        return f"{self.location}: {self.message}" if self.location else self.message


class UnknownReference(DomainError):  # noqa: N818, the name the brief and the domain use
    """Something names an identifier that does not exist where it should."""


class DuplicateId(DomainError):  # noqa: N818, paired with UnknownReference
    """An identifier or code that must be unique appears more than once."""
