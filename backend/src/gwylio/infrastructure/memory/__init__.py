"""In-memory implementations of the repository ports.

Used by the tests and by ``gwylio collect --dry-run``. They enforce the same
uniqueness rules the SQLite repositories will, so a test that passes here
describes behaviour persistence must keep.
"""

from gwylio.infrastructure.memory.repositories import (
    MemoryCandidateRepository,
    MemoryInstrumentRepository,
    MemoryScanRunRepository,
    MemorySourceRepository,
    NullKnownReports,
    StaticKnownReports,
)

__all__ = [
    "MemoryCandidateRepository",
    "MemoryInstrumentRepository",
    "MemoryScanRunRepository",
    "MemorySourceRepository",
    "NullKnownReports",
    "StaticKnownReports",
]
