"""Dissemination context: the products the register feeds.

Belongs here: the product model (``model``: strategic, operational INTSUM and
the tactical alert seam), the standing copy (``copy``), the plain views the
renderers read (``inputs``), the pure renderers (``render_intsum``,
``render_strategic``, ``render_tactical``) and the product file contract
(``product_file``). Rendering returns text; writing it to disk is
infrastructure. No prose is generated: every heading and standing sentence
comes from ``config/copy.json``.
"""
