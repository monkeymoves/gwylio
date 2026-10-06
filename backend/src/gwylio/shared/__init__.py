"""Shared kernel: value objects and the clock that every context may use.

Belongs here: small, frozen, I/O-free types with no domain policy of their own
(CleanText, CanonicalUrl, IsoDate, KebabId) and the Clock protocol. This
package imports no other gwylio package, so anything that needs a catalogue,
a requirement or a repository does not belong here.
"""
