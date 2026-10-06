"""Evaluation context: how well the collection is working.

Belongs here: funnel trends (``funnel``), yield per source (``yield_``), the
coverage audit that separates a quiet requirement from a blind spot
(``coverage``) and a count of the date check's findings (``datecheck``). Every
function is pure and takes plain records; the infrastructure layer reads the
database and the configuration and builds them. A requirement with low or no
scanability and no reports is a blind spot, never quiet.
"""
