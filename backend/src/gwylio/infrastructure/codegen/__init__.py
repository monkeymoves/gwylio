"""Code and document generators behind ``gwylio schema``.

Every generator is a pure function from already-loaded inputs to text, so
the drift test can render into a temporary directory and compare bytes with
the committed files. Output is deterministic.
"""
