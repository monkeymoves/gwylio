"""Domain errors carry a scope and a location and render them."""

from __future__ import annotations

from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference


def test_error_renders_location_then_message() -> None:
    error = UnknownReference("unknown lane 'x'", scope="actors", location="actors[2].lane")
    assert str(error) == "actors[2].lane: unknown lane 'x'"
    assert error.scope == "actors"
    assert error.message == "unknown lane 'x'"


def test_error_without_location_is_just_the_message() -> None:
    assert str(DuplicateId("twice")) == "twice"


def test_specific_errors_are_domain_errors() -> None:
    assert issubclass(UnknownReference, DomainError)
    assert issubclass(DuplicateId, DomainError)
