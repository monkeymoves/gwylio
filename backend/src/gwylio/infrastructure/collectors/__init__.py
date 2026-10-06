"""Concrete collectors, one adapter per discipline.

Belongs here: web search, site search, RSS and Atom feeds and the academic
indexes, each implementing the Collector port from the collection context, plus
the registry that maps disciplines to adapters. Collectors return hits; they
never score or tag them.
"""
